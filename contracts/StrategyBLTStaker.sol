// SPDX-License-Identifier: AGPL-3.0
pragma solidity ^0.8.15;

// These are the core Yearn libraries
import "@openzeppelin/contracts/utils/math/Math.sol";
import "@yearnvaults/contracts/BaseStrategy.sol";

interface IOracle {
    // pull our asset price, in usdc, via yearn's oracle
    function getPriceUsdcRecommended(
        address tokenAddress
    ) external view returns (uint256);
}

interface IMorphex is IERC20 {
    function claimable(address) external view returns (uint256);

    function pairAmounts(address) external view returns (uint256);

    function depositBalances(address, address) external view returns (uint256);

    function handleRewards(bool, bool, bool) external;

    function withdraw() external;

    function deposit(uint256) external;

    function signalTransfer(address) external;

    function acceptTransfer(address) external;

    function getPairAmount(address, uint256) external view returns (uint256);

    function mintAndStakeGlp(
        address,
        uint256,
        uint256,
        uint256
    ) external returns (uint256);

    function exercise(
        uint256 _amount,
        uint256 _profitSlippageAllowed,
        uint256 _swapSlippageAllowed
    ) external;
}

contract StrategyBLTStaker is BaseStrategy {
    using SafeERC20 for IERC20;
    /* ========== STATE VARIABLES ========== */

    /// @notice Morphex's reward router.
    /// @dev Used for staking/unstaking assets and claiming rewards.
    IMorphex public constant rewardRouter =
        IMorphex(0x49A97680938B4F1f73816d1B70C3Ab801FAd124B);

    /// @notice BLT, the LP token for the basket of collateral assets on Morphex.
    /// @dev This is staked for our want token.
    IMorphex public constant mlp =
        IMorphex(0xe771b4E273dF31B85D7A7aE0Efd22fb44BdD0633);

    /// @notice fsBLT, the representation of our staked BLT that the strategy holds.
    IMorphex public constant fsMlp =
        IMorphex(0x2D5875ab0eFB999c1f49C798acb9eFbd1cfBF63c);

    /// @notice fBLT, used to check for claimable rewards
    IMorphex public constant fMlp =
        IMorphex(0xa2242d0A8b0b5c1A487AbFC03Cd9FEf6262BAdCA);

    /// @notice Address for WETH, our fee token.
    IERC20 public constant weth =
        IERC20(0x4200000000000000000000000000000000000006);

    /// @notice Address for oBMX, our option token (received as rewards).
    IERC20 public constant oBMX =
        IERC20(0x3Ff7AB26F2dfD482C40bDaDfC0e88D01BFf79713);

    /// @notice Helper contract to sell oBMX for WETH.
    IMorphex public constant exerciseHelperBMX =
        IMorphex(0x7103834002CE76ad0BCb18dDB579c1266E1A925b);

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
        address mlpManager = 0x9fAc7b75f367d5B35a6D6D0a09572eFcC3D406C5;
        weth.approve(address(mlpManager), type(uint256).max);
        oBMX.approve(address(exerciseHelperBMX), type(uint256).max);

        // set up our max delay
        maxReportDelay = 7 days;

        // set our min and max profit
        harvestProfitMinInUsdc = 1_000e6;
        harvestProfitMaxInUsdc = 10_000e6;

        // set our strategy's name
        stratName = "StrategyBLTStaker";
    }

    /* ========== VIEWS ========== */

    /// @notice Strategy name.
    function name() external view override returns (string memory) {
        return stratName;
    }

    /// @notice Total assets the strategy holds.
    function estimatedTotalAssets() public view override returns (uint256) {
        return fsMlp.balanceOf(address(this));
    }

    /// @notice Balance of oBMX sitting in our strategy.
    function balanceOfoBmx() public view returns (uint256) {
        return oBMX.balanceOf(address(this));
    }

    /// @notice Balance of WETH sitting in our strategy.
    function balanceOfoWeth() public view returns (uint256) {
        return weth.balanceOf(address(this));
    }

    /// @notice Balance of WETH claimable from BLT fees.
    function claimableWeth() public view returns (uint256) {
        return fMlp.claimable(address(this));
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
    function exercise(
        uint256 _profitSlippage,
        uint256 _swapSlippage
    ) external onlyVaultManagers {
        // exercise oBMX for WETH if we have enough
        uint256 toExercise = balanceOfoBmx();
        if (toExercise > 0) {
            exerciseHelperBMX.exercise(
                toExercise,
                _profitSlippage,
                _swapSlippage
            );
        }
    }

    /// @notice Provide any loose WETH to BLT and stake it.
    /// @dev May only be called by vault managers.
    /// @return Amount of BLT staked from profits.
    function mintAndStake() external onlyVaultManagers returns (uint256) {
        uint256 wethBalance = balanceOfoWeth();
        uint256 newMlp;

        // deposit our WETH to BLT
        if (wethBalance > 0) {
            newMlp = rewardRouter.mintAndStakeGlp(
                address(weth),
                wethBalance,
                0,
                0
            );
        }
        return newMlp;
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
        uint256 wethBalance = balanceOfoWeth();
        if (wethBalance > 0) {
            weth.safeTransfer(_newStrategy, wethBalance);
        }

        uint256 oBmxBalance = balanceOfoBmx();
        if (oBmxBalance > 0) {
            oBMX.safeTransfer(_newStrategy, oBmxBalance);
        }
    }

    /// @notice Part 1 of our strategy migration. Pull it out manually for migrating to new want
    /// @dev May only be called by governance.
    /// @param _newStrategy Address of the new strategy we are migrating to.
    function manualTransfer(address _newStrategy) external onlyGovernance {
        rewardRouter.signalTransfer(_newStrategy);
    }

    /// @notice Part 2 of our strategy migration. Must do before harvesting the new strategy.
    /// @dev May only be called by governance.
    /// @param _oldStrategy Address of the old strategy we are migrating from.
    function acceptTransfer(address _oldStrategy) external onlyGovernance {
        rewardRouter.acceptTransfer(_oldStrategy);
    }

    /// @notice Manually claim our rewards.
    /// @dev May only be called by vault managers.
    function handleRewards() external onlyVaultManagers {
        _handleRewards();
    }

    function _handleRewards() internal onlyVaultManagers {
        // claim oBMX, claim WETH, convert WETH to ETH
        rewardRouter.handleRewards(true, true, false);
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
    /// @dev Uses yearn's lens oracle, if returned values are strange then troubleshoot there.
    /// @return Total return in USDC from selling claimable WETH.
    function claimableProfitInUsdc() public view returns (uint256) {
        IOracle yearnOracle = IOracle(
            0xE0F3D78DB7bC111996864A32d22AB0F59Ca5Fa86
        ); // yearn lens oracle
        uint256 wethPrice = yearnOracle.getPriceUsdcRecommended(address(weth));

        // Oracle returns prices as 6 decimals, so multiply by claimable amount and divide by token decimals (1e18)
        return (wethPrice * claimableWeth()) / 1e18;
    }

    /// @notice Convert our keeper's eth cost into want
    /// @dev We don't use this since we don't factor call cost into our harvestTrigger.
    /// @param _ethAmount Amount of ether spent.
    /// @return Value of ether in want.
    function ethToWant(
        uint256 _ethAmount
    ) public view override returns (uint256) {}

    // include so our contract plays nicely with ftm
    receive() external payable {}

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
