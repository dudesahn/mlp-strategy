import pytest
from brownie import config, Contract, ZERO_ADDRESS, chain, interface, accounts
import requests


@pytest.fixture(scope="function", autouse=True)
def isolate(fn_isolation):
    pass


# set this for if we want to use tenderly or not; mostly helpful because with brownie.reverts fails in tenderly forks.
# for this repo, especially helper with the long swap router test
use_tenderly = False

# use this to set what chain we use. 1 for ETH, 250 for fantom, 10 optimism, 42161 arbitrum, 8453 base, 34443 mode
chain_used = 34443


@pytest.fixture(scope="session")
def tests_using_tenderly():
    yes_or_no = use_tenderly
    yield yes_or_no


################################################## TENDERLY DEBUGGING ##################################################


# change autouse to True if we want to use this fork to help debug tests
@pytest.fixture(scope="session", autouse=use_tenderly)
def tenderly_fork(web3, chain):
    import requests
    import os

    # Get env variables
    TENDERLY_ACCESS_KEY = os.environ.get("TENDERLY_ACCESS_KEY")
    TENDERLY_USER = os.environ.get("TENDERLY_USER")
    TENDERLY_PROJECT = os.environ.get("TENDERLY_PROJECT")

    # Construct request
    url = f"https://api.tenderly.co/api/v1/account/{TENDERLY_USER}/project/{TENDERLY_PROJECT}/fork"
    headers = {"X-Access-Key": str(TENDERLY_ACCESS_KEY)}
    data = {
        "network_id": str(chain.id),
    }

    # Post request
    response = requests.post(url, json=data, headers=headers)

    # Parse response
    fork_id = response.json()["simulation_fork"]["id"]

    # Set provider to your new Tenderly fork
    fork_rpc_url = f"https://rpc.tenderly.co/fork/{fork_id}"
    tenderly_provider = web3.HTTPProvider(fork_rpc_url, {"timeout": 600})
    web3.provider = tenderly_provider
    print(
        f"https://dashboard.tenderly.co/{TENDERLY_USER}/{TENDERLY_PROJECT}/fork/{fork_id}"
    )


################################################ UPDATE THINGS BELOW HERE ################################################

#################### FIXTURES BELOW NEED TO BE ADJUSTED FOR THIS REPO ####################


# if we want to make harvests public, then we should prevent same-block reward claiming and minting to be safe, but realistically just put it on a gelato job that scream tops up from time to time


@pytest.fixture(scope="session")
def token():
    token_address = "0x0Eb231766cD891ed6aA4FafEeF60E1c01b18c12a"  # this should be the address of the ERC-20 used by the strategy/vault (sMLT)
    yield interface.IERC20(token_address)


@pytest.fixture(scope="session")
def whale(amount, token):
    # Totally in it for the tech
    # Update this with a large holder of your want token (the largest EOA holder of LP)
    whale = accounts.at(
        "0xB1dD2Fdb023cB54b7cc2a0f5D9e8d47a9F7723ce", force=True
    )  # 0xB1dD2Fdb023cB54b7cc2a0f5D9e8d47a9F7723ce, fsMLT, 61
    if token.balanceOf(whale) < 2 * amount:
        raise ValueError(
            "Our whale needs more funds. Find another whale or reduce your amount variable."
        )
    yield whale


@pytest.fixture(scope="session")
def amount(token):
    amount = 30 * 10 ** token.decimals()
    yield amount


@pytest.fixture(scope="session")
def profit_whale(profit_amount, token):
    # ideally not the same whale as the main whale, or else they will lose money
    profit_whale = accounts.at(
        "0xB1dD2Fdb023cB54b7cc2a0f5D9e8d47a9F7723ce", force=True
    )  # 0xB1dD2Fdb023cB54b7cc2a0f5D9e8d47a9F7723ce, fsMLT, 61 tokens
    if token.balanceOf(profit_whale) < 5 * profit_amount:
        raise ValueError(
            "Our profit whale needs more funds. Find another whale or reduce your profit_amount variable."
        )
    yield profit_whale


@pytest.fixture(scope="session")
def profit_amount(token):
    profit_amount = 0.1 * 10 ** token.decimals()
    yield profit_amount


# set address if already deployed, use ZERO_ADDRESS if not
@pytest.fixture(scope="session")
def vault_address():
    vault_address = ZERO_ADDRESS
    yield vault_address


# if our vault is pre-0.4.3, this will affect a few things
@pytest.fixture(scope="session")
def old_vault():
    old_vault = False
    yield old_vault


# this is the name we want to give our strategy
@pytest.fixture(scope="session")
def strategy_name():
    strategy_name = "StrategyMLTStaker"
    yield strategy_name


# this is the name of our strategy in the .sol file
@pytest.fixture(scope="session")
def contract_name(StrategyMLTStaker):
    contract_name = StrategyMLTStaker
    yield contract_name


# if our strategy is using ySwaps, then we will treat it differently and will have async profit/rewards claiming
@pytest.fixture(scope="session")
def use_yswaps():
    use_yswaps = True
    yield use_yswaps


# whether or not a strategy is clonable. if true, don't forget to update what our cloning function is called in test_cloning.py
@pytest.fixture(scope="session")
def is_clonable():
    is_clonable = False
    yield is_clonable


# use this to test our strategy in case there are no profits
@pytest.fixture(scope="session")
def no_profit():
    no_profit = False
    yield no_profit


# use this when we might lose a few wei on conversions between want and another deposit token (like router strategies)
# generally this will always be true if no_profit is true, even for curve/convex since we can lose a wei converting
@pytest.fixture(scope="session")
def is_slippery(no_profit):
    is_slippery = False  # set this to true or false as needed
    if no_profit:
        is_slippery = True
    yield is_slippery


# use this to set the standard amount of time we sleep between harvests.
# generally 1 day, but can be less if dealing with smaller windows (oracles) or longer if we need to trigger weekly earnings.
@pytest.fixture(scope="session")
def sleep_time():
    hour = 1

    # change this one right here
    hours_to_sleep = 48

    sleep_time = hour * hours_to_sleep
    yield sleep_time


#################### FIXTURES ABOVE NEED TO BE ADJUSTED FOR THIS REPO ####################

#################### FIXTURES BELOW SHOULDN'T NEED TO BE ADJUSTED FOR THIS REPO ####################


@pytest.fixture(scope="session")
def tests_using_tenderly():
    yes_or_no = use_tenderly
    yield yes_or_no


@pytest.fixture(scope="session")
def RELATIVE_APPROX():
    yield 10


# use this to set various fixtures that differ by chain
if chain_used == 1:  # mainnet

    @pytest.fixture(scope="session")
    def gov():
        yield accounts.at("0xFEB4acf3df3cDEA7399794D0869ef76A6EfAff52", force=True)

    @pytest.fixture(scope="session")
    def health_check():
        yield interface.IHealthCheck("0xddcea799ff1699e98edf118e0629a974df7df012")

    @pytest.fixture(scope="session")
    def base_fee_oracle():
        yield interface.IBaseFeeOracle("0xfeCA6895DcF50d6350ad0b5A8232CF657C316dA7")

    # set all of the following to SMS, just simpler
    @pytest.fixture(scope="session")
    def management():
        yield accounts.at("0x16388463d60FFE0661Cf7F1f31a7D658aC790ff7", force=True)

    @pytest.fixture(scope="session")
    def rewards(management):
        yield management

    @pytest.fixture(scope="session")
    def guardian(management):
        yield management

    @pytest.fixture(scope="session")
    def strategist(management):
        yield management

    @pytest.fixture(scope="session")
    def keeper(management):
        yield management

    @pytest.fixture(scope="session")
    def to_sweep():
        # token we can sweep out of strategy (use CRV)
        yield interface.IERC20("0xD533a949740bb3306d119CC777fa900bA034cd52")

    @pytest.fixture(scope="session")
    def trade_factory():
        yield Contract("0xcADBA199F3AC26F67f660C89d43eB1820b7f7a3b")

    @pytest.fixture(scope="session")
    def keeper_wrapper():
        yield Contract("0x0D26E894C2371AB6D20d99A65E991775e3b5CAd7")

elif chain_used == 250:  # fantom

    @pytest.fixture(scope="session")
    def gov():
        yield accounts.at("0x63A03871141D88cB5417f18DD5b782F9C2118b5B", force=True)

    @pytest.fixture(scope="session")
    def health_check():
        yield interface.IHealthCheck("0xf13Cd6887C62B5beC145e30c38c4938c5E627fe0")

    @pytest.fixture(scope="session")
    def base_fee_oracle():
        yield interface.IBaseFeeOracle("0xa11E8b010164C1B58b43527D0fDD369845d6ec4A")

    # set all of the following to Scream Guardian MS
    @pytest.fixture(scope="session")
    def management():
        yield accounts.at("0x52baD1537790f102012f4D10B887AE2E5819563F", force=True)

    @pytest.fixture(scope="session")
    def rewards(management):
        yield management

    @pytest.fixture(scope="session")
    def guardian(management):
        yield management

    @pytest.fixture(scope="session")
    def strategist(management):
        yield management

    @pytest.fixture(scope="session")
    def keeper(management):
        yield management

    @pytest.fixture(scope="session")
    def to_sweep():
        # token we can sweep out of strategy (use CRV)
        yield interface.IERC20("0x1E4F97b9f9F913c46F1632781732927B9019C68b")

    # deploy this eventually

    @pytest.fixture(scope="session")
    def keeper_wrapper():
        yield to_sweep

    @pytest.fixture(scope="session")
    def trade_factory():
        yield to_sweep

elif chain_used == 8453:  # base

    @pytest.fixture(scope="function")
    def gov():  # BMX multisig 0xE02Fb5C70aF32F80Aa7F9E8775FE7F12550348ec
        yield accounts.at("0xE02Fb5C70aF32F80Aa7F9E8775FE7F12550348ec", force=True)

    @pytest.fixture(scope="session")
    def health_check():
        yield interface.IHealthCheck("0x8273217252254Ad7353f227aaEcd2b1C4A326Fa2")

    @pytest.fixture(scope="session")
    def base_fee_oracle():
        yield interface.IBaseFeeOracle("0x298Bd23E25C01440D68d4D2708bFf6A7E10a1db5")

    # set all of the following to Scream Guardian MS
    @pytest.fixture(scope="session")
    def management():
        yield accounts.at("0x89955a99552F11487FFdc054a6875DF9446B2902", force=True)

    @pytest.fixture(scope="session")
    def rewards(management):
        yield management

    @pytest.fixture(scope="session")
    def guardian(management):
        yield management

    @pytest.fixture(scope="session")
    def strategist(management):
        yield management

    @pytest.fixture(scope="session")
    def keeper(management):
        yield management

    @pytest.fixture(scope="session")
    def to_sweep():
        # token we can sweep out of strategy (use DAI)
        yield interface.IERC20("0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb")

    # deploy this eventually

    @pytest.fixture(scope="session")
    def keeper_wrapper():
        yield to_sweep

    @pytest.fixture(scope="session")
    def trade_factory():
        yield to_sweep

elif chain_used == 34443:  # mode

    @pytest.fixture(scope="session")
    def gov():  # BMX multisig 0x99FC968d932f394256e536B5dF3A6e2C8aa2DD36
        yield accounts.at("0x99FC968d932f394256e536B5dF3A6e2C8aa2DD36", force=True)

    # set all of the following to Scream Guardian MS
    @pytest.fixture(scope="session")
    def management():
        yield accounts.at("0x89955a99552F11487FFdc054a6875DF9446B2902", force=True)

    @pytest.fixture(scope="session")
    def rewards(management):
        yield management

    @pytest.fixture(scope="session")
    def guardian(management):
        yield management

    @pytest.fixture(scope="session")
    def strategist(management):
        yield management

    @pytest.fixture(scope="session")
    def keeper(management):
        yield management

    @pytest.fixture(scope="session")
    def to_sweep():
        # token we can sweep out of strategy (use DAI)
        yield interface.IERC20("0x50c5725949A6F0c72E6C4a641F24049A917DB0Cb")

    # deploy this eventually

    @pytest.fixture(scope="session")
    def keeper_wrapper():
        yield to_sweep

    @pytest.fixture(scope="session")
    def trade_factory():
        yield to_sweep

    @pytest.fixture(scope="session")
    def weth():
        yield Contract("0x4200000000000000000000000000000000000006")


@pytest.fixture(scope="module")
def vault(pm, gov, rewards, guardian, management, token, vault_address):
    if vault_address == ZERO_ADDRESS:
        Vault = pm(config["dependencies"][0]).Vault
        vault = guardian.deploy(Vault)
        vault.initialize(token, gov, rewards, "", "", guardian)
        vault.setDepositLimit(2**256 - 1, {"from": gov})
        vault.setManagement(management, {"from": gov})
    else:
        vault = interface.IVaultFactory045(vault_address)
    yield vault


#################### FIXTURES ABOVE SHOULDN'T NEED TO BE ADJUSTED FOR THIS REPO ####################

#################### FIXTURES BELOW LIKELY NEED TO BE ADJUSTED FOR THIS REPO ####################


@pytest.fixture(scope="session")
def target():
    # whatever we want it to be—this is passed into our harvest function as a target
    yield 7


# this should be a strategy from a different vault to check during migration
@pytest.fixture(scope="session")
def other_strategy():
    yield Contract("0x49D8b010243a4aD4B1dF53E3B3a2986861A0C8c3")


@pytest.fixture
def strategy(
    strategist,
    keeper,
    vault,
    gov,
    management,
    contract_name,
    strategy_name,
    vault_address,
    trade_factory,
    to_vest,
    weth,
):
    # will need to update this based on the strategy's constructor ******
    strategy = gov.deploy(contract_name, vault)

    strategy.setKeeper(keeper, {"from": gov})
    vault.setPerformanceFee(0, {"from": gov})
    vault.setManagementFee(0, {"from": gov})

    vault.addStrategy(strategy, 10_000, 0, 2**256 - 1, 0, {"from": gov})

    # turn our oracle into testing mode by setting the provider to 0x00, then forcing true
    assert strategy.isBaseFeeAcceptable() == True

    yield strategy


#################### FIXTURES ABOVE LIKELY NEED TO BE ADJUSTED FOR THIS REPO ####################

####################         PUT UNIQUE FIXTURES FOR THIS REPO BELOW         ####################


# use this similarly to how we use use_yswaps
@pytest.fixture(scope="session")
def is_gmx():
    yield True


# use this to set what percentage of our esMPX we vest (0, 10%, 50%)
@pytest.fixture(scope="session")
def to_vest():
    yield 0


# our wMLP oracle
@pytest.fixture(scope="function")
def oracle(wMlpPessimisticOracle, guardian, strategy, vault):
    oracle = guardian.deploy(
        wMlpPessimisticOracle,
        "0xA3Ea99f8aE06bA0d9A6Cf7618d06AEa4564340E9",
        strategy.mlp(),
        vault.address,
    )
    yield oracle


@pytest.fixture(scope="session")
def destination_strategy():
    # destination strategy of the route
    yield interface.ICurveStrategy045("0x49D8b010243a4aD4B1dF53E3B3a2986861A0C8c3")


@pytest.fixture(
    params=[
        True,
        False,
    ],
    ids=["receive_underlying", "receive_weth"],
    scope="function",
)
def receive_underlying(request):
    yield request.param


@pytest.fixture(
    params=[
        True,
        False,
    ],
    ids=["round_up", "round_down"],
    scope="function",
)
def round_up(request):
    yield request.param


@pytest.fixture(
    params=[
        True,
        False,
    ],
    ids=["yes_test_swap", "no_test_swap"],
    scope="function",
)
def test_swap(request):
    yield request.param


if chain_used == 8453:
    # use these for our BLT router testing
    @pytest.fixture(scope="function")
    def router(wBLTRouter, screamsh):
        router = screamsh.deploy(wBLTRouter)
        # router = Contract("0x70FfF9B84788566065f1dFD8968Fb72F798b9aE5")  # v22, testing
        yield router

    @pytest.fixture(scope="function")
    def screamsh():
        yield accounts.at("0x89955a99552F11487FFdc054a6875DF9446B2902", force=True)

    @pytest.fixture(scope="function")
    def w_blt():
        yield Contract("0x4E74D4Db6c0726ccded4656d0BCE448876BB4C7A")

    @pytest.fixture(scope="function")
    def gauge():
        yield Contract("0x1F7B5E65c09dF12742255BB8Fe26958f4B52F9bb")

    @pytest.fixture(scope="function")
    def weth():
        yield Contract("0x4200000000000000000000000000000000000006")

    @pytest.fixture(scope="function")
    def bmx():
        yield Contract("0x548f93779fBC992010C07467cBaf329DD5F059B7")

    @pytest.fixture(scope="function")
    def factory():
        yield "0xe21Aac7F113Bd5DC2389e4d8a8db854a87fD6951"

    @pytest.fixture(scope="function")
    def obmx():
        yield Contract("0x3Ff7AB26F2dfD482C40bDaDfC0e88D01BFf79713")

    @pytest.fixture(scope="function")
    def usdc():
        yield Contract("0xd9aAEc86B65D86f6A7B5B1b0c42FFA531710b6CA")

    @pytest.fixture(scope="function")
    def bvm():
        yield interface.IERC20("0xd386a121991E51Eab5e3433Bf5B1cF4C8884b47a")

    @pytest.fixture(scope="function")
    def obvm():
        yield Contract("0x762eb51D2e779EeEc9B239FFB0B2eC8262848f3E")

    @pytest.fixture(scope="function")
    def weth_whale():
        yield accounts.at("0xB4885Bc63399BF5518b994c1d0C153334Ee579D0", force=True)

    # route to swap from wBLT to WETH
    @pytest.fixture(scope="function")
    def wblt_route(w_blt, weth):
        wblt_route = [
            (w_blt.address, weth.address, False),
        ]
        yield wblt_route

    # route to swap from WETH to wBLT
    @pytest.fixture(scope="function")
    def weth_route(w_blt, weth):
        weth_route = [
            (weth.address, w_blt.address, False),
        ]
        yield weth_route

    # our dump helper
    @pytest.fixture(scope="function")
    def bvm_exercise_helper(SimpleExerciseHelperWETH, guardian):
        bvm_exercise_helper = guardian.deploy(
            SimpleExerciseHelperWETH,
        )
        yield bvm_exercise_helper

    # our dump helper
    @pytest.fixture(scope="function")
    def bmx_exercise_helper(
        wBLTExerciseHelper, guardian, router, wblt_route, weth_route
    ):
        #         bmx_exercise_helper = wBLTExerciseHelper.at(
        #             "0x99413e382629be72F89D80CCEEF40Fe80CF3934f"
        #         )
        bmx_exercise_helper = guardian.deploy(
            wBLTExerciseHelper, wblt_route, weth_route
        )
        yield bmx_exercise_helper
