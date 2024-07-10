// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.15;

import "@openzeppelin/contracts@4.9.3/utils/math/Math.sol";
import "@yearnvaults/contracts/BaseStrategy.sol";

interface IOracle {
    function latestAnswer() external view returns (int256);
}

interface IMorphex is IERC20 {
    function claimable(address) external view returns (uint256);

    function handleRewards(bool, bool, bool, bool) external;

    function mintAndStakeBlt(
        address,
        uint256,
        uint256,
        uint256
    ) external returns (uint256);
}

contract StrategyMLTStaker is BaseStrategy {
    using SafeERC20 for IERC20;
    /* ========== STATE VARIABLES ========== */

    /// @notice Morphex's reward router.
    /// @dev Used for staking/unstaking assets and claiming rewards.
    IMorphex public constant rewardRouter =
        IMorphex(0x73bF80506F891030570FDC4D53a71f44a442353C);

    /// @notice BLT, the LP token for the basket of collateral assets on Morphex.
    /// @dev This is staked for our want token.
    IMorphex public constant mlt =
        IMorphex(0x952AdBB385296Dcf86a668f7eaa02DF7eb684439);

    /// @notice fsBLT, the representation of our staked BLT that the strategy holds.
    IMorphex public constant fsMlt =
        IMorphex(0x6c72ADbDc1029ee901dC97C5604487285D972A4f);

    /// @notice used to track claimable WETH
    IMorphex public constant fMlt =
        IMorphex(0xCcBF79AA51919f1711E40293a32bbC71F8842FC3);

    /// @notice Address for WETH, our fee token.
    IERC20 public constant weth =
        IERC20(0x4200000000000000000000000000000000000006);

    /// @notice Minimum profit size in USDC that we want to harvest.
    /// @dev Only used in harvestTrigger.
    uint256 public harvestProfitMinInUsdc;

    /// @notice Maximum profit size in USDC that we want to harvest (ignore gas price once we get here).
    /// @dev Only used in harvestTrigger.
    uint256 public harvestProfitMaxInUsdc;

    // we use this to be able to adjust our strategy's name
    string internal stratName;

    // this means all of our fee values are in basis points
    uint256 internal constant FEE_DENOMINATOR = 10_000;

    /* ========== CONSTRUCTOR ========== */

    constructor(address _vault) BaseStrategy(_vault) {
        // want = sBLT
        address mltManager = 0xf9Fc0B2859f9B6d33fD1Cea5B0A9f1D56C258178;
        weth.approve(address(mltManager), type(uint256).max);

        // set up our max delay
        maxReportDelay = 7 days;

        // set our min and max profit
        harvestProfitMinInUsdc = 1_000e6;
        harvestProfitMaxInUsdc = 10_000e6;

        // set our strategy's name
        stratName = "StrategyMLTStaker";
    }

    /* ========== VIEWS ========== */

    /// @notice Strategy name.
    function name() external view override returns (string memory) {
        return stratName;
    }

    /// @notice Total assets the strategy holds.
    function estimatedTotalAssets() public view override returns (uint256) {
        return fsMlt.balanceOf(address(this));
    }

    /// @notice Balance of WETH sitting in our strategy.
    function balanceOfWeth() public view returns (uint256) {
        return weth.balanceOf(address(this));
    }

    /// @notice Balance of WETH claimable from BLT fees.
    function claimableWeth() public view returns (uint256) {
        return fMlt.claimable(address(this));
    }

    /* ========== CORE STRATEGY FUNCTIONS ========== */

    function prepareReturn(
        uint256 _debtOutstanding
    )
        internal
        override
        returns (uint256 _profit, uint256 _loss, uint256 _debtPayment)
    {
        // don't convert to ETH, leave as WETH
        _handleRewards();

        // serious loss should never happen, but if it does, let's record it accurately
        uint256 assets = estimatedTotalAssets();
        uint256 debt = vault.strategies(address(this)).totalDebt;

        // if assets are greater than debt, things are working great!
        if (assets >= debt) {
            unchecked {
                _profit = assets - debt;
            }
            _debtPayment = _debtOutstanding;

            uint256 toFree = _profit + _debtPayment;

            // freed is math.min(wantBalance, toFree)
            (uint256 freed, ) = liquidatePosition(toFree);

            if (toFree > freed) {
                if (_debtPayment > freed) {
                    _debtPayment = freed;
                    _profit = 0;
                } else {
                    unchecked {
                        _profit = freed - _debtPayment;
                    }
                }
            }
        }
        // if assets are less than debt, we are in trouble. don't worry about withdrawing here, just report losses
        else {
            unchecked {
                _loss = debt - assets;
            }
        }
    }

    /// @notice Provide any loose WETH to BLT and stake it.
    /// @dev May only be called by vault managers.
    /// @return Amount of BLT staked from profits.
    function mintAndStake() external onlyVaultManagers returns (uint256) {
        uint256 wethBalance = balanceOfWeth();
        uint256 newMlt;

        // deposit our WETH to BLT
        if (wethBalance > 0) {
            newMlt = rewardRouter.mintAndStakeBlt(
                address(weth),
                wethBalance,
                0,
                0
            );
        }
        return newMlt;
    }

    function adjustPosition(uint256 _debtOutstanding) internal override {
        // if in emergency exit, we don't want to deploy any more funds
        if (emergencyExit) {
            return;
        }
    }

    function liquidatePosition(
        uint256 _amountNeeded
    ) internal override returns (uint256 _liquidatedAmount, uint256 _loss) {
        // check our "loose" want
        uint256 _wantBal = estimatedTotalAssets();
        if (_amountNeeded > _wantBal) {
            uint256 _withdrawnBal = estimatedTotalAssets();
            _liquidatedAmount = Math.min(_amountNeeded, _withdrawnBal);
            unchecked {
                _loss = _amountNeeded - _liquidatedAmount;
            }
        } else {
            // we have enough balance to cover the liquidation available
            return (_amountNeeded, 0);
        }
    }

    // fire sale, get rid of it all!
    function liquidateAllPositions() internal override returns (uint256) {
        return estimatedTotalAssets();
    }

    // want is blocked by default, add any other tokens to protect from gov here.
    function protectedTokens()
        internal
        view
        override
        returns (address[] memory)
    {}

    // migrate our want token to a new strategy if needed
    function prepareMigration(address _newStrategy) internal override {
        uint256 wethBalance = balanceOfWeth();
        if (wethBalance > 0) {
            weth.safeTransfer(_newStrategy, wethBalance);
        }
    }

    /// @notice Manually claim our rewards.
    /// @dev May only be called by vault managers.
    function handleRewards() external onlyVaultManagers {
        _handleRewards();
    }

    function _handleRewards() internal {
        // claim opBMX, stake mul points, claim WETH, convert WETH to ETH
        rewardRouter.handleRewards(true, true, true, false);
    }

    /* ========== KEEP3RS ========== */

    /**
     * @notice
     *  Provide a signal to the keeper that harvest() should be called.
     *
     *  Don't harvest if a strategy is inactive.
     *  If our profit exceeds our upper limit, then harvest no matter what. For
     *  our lower profit limit, credit threshold, max delay, and manual force trigger,
     *  only harvest if our gas price is acceptable.
     *
     * @param callCostinEth The keeper's estimated gas cost to call harvest() (in wei).
     * @return True if harvest() should be called, false otherwise.
     */
    function harvestTrigger(
        uint256 callCostinEth
    ) public view override returns (bool) {
        // Should not trigger if strategy is not active (no assets and no debtRatio). This means we don't need to adjust keeper job.
        if (!isActive()) {
            return false;
        }

        // harvest if we have a profit to claim at our upper limit without considering gas price
        uint256 claimableProfit = claimableProfitInUsdc();
        if (claimableProfit > harvestProfitMaxInUsdc) {
            return true;
        }

        // check if the base fee gas price is higher than we allow. if it is, block harvests.
        if (!isBaseFeeAcceptable()) {
            return false;
        }

        // trigger if we want to manually harvest, but only if our gas price is acceptable
        if (forceHarvestTriggerOnce) {
            return true;
        }

        // harvest if we have a sufficient profit to claim, but only if our gas price is acceptable
        if (claimableProfit > harvestProfitMinInUsdc) {
            return true;
        }

        StrategyParams memory params = vault.strategies(address(this));
        // harvest regardless of profit once we reach our maxDelay
        if (block.timestamp - params.lastReport > maxReportDelay) {
            return true;
        }

        // harvest our credit if it's above our threshold
        if (vault.creditAvailable() > creditThreshold) {
            return true;
        }

        // otherwise, we don't harvest
        return false;
    }

    /// @notice Calculates the profit if all claimable assets were sold for USDC (6 decimals).
    /// @dev Uses wrapper for Redstone WETH oracle.
    /// @return Total return in USDC from selling claimable WETH.
    function claimableProfitInUsdc() public view returns (uint256) {
        IOracle oracle = IOracle(0x37E4e0B01773Bb7A09eA0265eD04A18700A40801);
        uint256 wethPrice = uint256(oracle.latestAnswer());

        // Oracle returns prices as 8 decimals, so multiply by claimable amount and divide by token decimals * 1e2
        return (wethPrice * claimableWeth()) / 1e20;
    }

    /// @notice Convert our keeper's eth cost into want
    /// @dev We don't use this since we don't factor call cost into our harvestTrigger.
    /// @param _ethAmount Amount of ether spent.
    /// @return Value of ether in want.
    function ethToWant(
        uint256 _ethAmount
    ) public view override returns (uint256) {}

    /* ========== SETTERS ========== */
    // These functions are useful for setting parameters of the strategy that may need to be adjusted.

    /**
     * @notice
     *  Here we set various parameters to optimize our harvestTrigger.
     * @param _harvestProfitMinInUsdc The amount of profit (in USDC, 6 decimals)
     *  that will trigger a harvest if gas price is acceptable.
     * @param _harvestProfitMaxInUsdc The amount of profit in USDC that
     *  will trigger a harvest regardless of gas price.
     */
    function setHarvestTriggerParams(
        uint256 _harvestProfitMinInUsdc,
        uint256 _harvestProfitMaxInUsdc
    ) external onlyVaultManagers {
        harvestProfitMinInUsdc = _harvestProfitMinInUsdc;
        harvestProfitMaxInUsdc = _harvestProfitMaxInUsdc;
    }
}
