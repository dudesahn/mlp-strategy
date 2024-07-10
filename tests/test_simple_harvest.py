from brownie import chain, Contract
from utils import harvest_strategy
import pytest


# test the our strategy's ability to deposit, harvest, and withdraw, with different optimal deposit tokens if we have them
def test_simple_harvest(
    gov,
    token,
    vault,
    whale,
    strategy,
    amount,
    sleep_time,
    is_slippery,
    no_profit,
    profit_whale,
    profit_amount,
    target,
    use_yswaps,
    is_gmx,
    RELATIVE_APPROX,
):
    ## deposit to the vault after approving
    starting_whale = token.balanceOf(whale)
    token.approve(vault, 2**256 - 1, {"from": whale})
    rewards = vault.rewards()

    print(
        "Before deposit Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards) / 1e18,
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    vault.deposit(amount, {"from": whale})
    newWhale = token.balanceOf(whale)

    print(
        "After deposit Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # shouldn't have anything claimable before we deposit
    assert strategy.claimableWeth() == 0

    # harvest, store asset amount
    (profit, loss, extra) = harvest_strategy(
        is_gmx,
        strategy,
        token,
        gov,
        profit_whale,
        profit_amount,
        target,
    )
    print("Profit:", profit)
    old_assets = vault.totalAssets()
    assert old_assets > 0
    assert strategy.estimatedTotalAssets() > 0

    print(
        "After first harvest Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # simulate profits
    chain.sleep(sleep_time)
    assert strategy.claimableWeth() > 0
    print("🚨🚨🚨 Claimable WETH:", strategy.claimableWeth())
    print(" Claimable in USDC:", strategy.claimableProfitInUsdc())

    # harvest, store new asset amount
    (profit, loss, extra) = harvest_strategy(
        is_gmx,
        strategy,
        token,
        gov,
        profit_whale,
        profit_amount,
        target,
    )

    print("Profit:", profit / 1e18)

    # loose WETH, profitable harvest, or assets that will be taken as profit next harvest
    assert (
        strategy.balanceOfWeth() > 0
        or profit > 0
        or strategy.estimatedTotalAssets() > vault.totalAssets()
    )

    # record this here so it isn't affected if we donate via ySwaps
    strategy_assets = strategy.estimatedTotalAssets()

    print(
        "After second harvest Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # harvest again so the strategy reports the profit
    if use_yswaps or is_gmx:
        print("Using ySwaps for harvests")
        (profit, loss, extra) = harvest_strategy(
            is_gmx,
            strategy,
            token,
            gov,
            profit_whale,
            profit_amount,
            target,
        )
        print("Profit:", profit / 1e18)

    # evaluate our current total assets
    new_assets = vault.totalAssets()

    # WHY DOES THIS GO NEGATIVE LMAO
    print(
        "After third harvest vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # simulate profits
    chain.sleep(sleep_time)

    # harvest, store new asset amount
    (profit, loss, extra) = harvest_strategy(
        is_gmx,
        strategy,
        token,
        gov,
        profit_whale,
        profit_amount,
        target,
    )
    print("Profit:", profit / 1e18)
    # record this here so it isn't affected if we donate via ySwaps
    strategy_assets = strategy.estimatedTotalAssets()

    print(
        "After fourth harvest Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # simulate profits
    chain.sleep(sleep_time)

    # harvest, store new asset amount
    (profit, loss, extra) = harvest_strategy(
        is_gmx,
        strategy,
        token,
        gov,
        profit_whale,
        profit_amount,
        target,
    )
    print("Profit:", profit / 1e18)
    # record this here so it isn't affected if we donate via ySwaps
    strategy_assets = strategy.estimatedTotalAssets()

    print(
        "After fifth harvest Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # simulate profits
    chain.sleep(sleep_time)

    # harvest, store new asset amount
    (profit, loss, extra) = harvest_strategy(
        is_gmx,
        strategy,
        token,
        gov,
        profit_whale,
        profit_amount,
        target,
    )
    print("Profit:", profit / 1e18)
    # record this here so it isn't affected if we donate via ySwaps
    strategy_assets = strategy.estimatedTotalAssets()

    print(
        "After sixth harvest Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # simulate profits
    chain.sleep(sleep_time)

    # harvest, store new asset amount
    (profit, loss, extra) = harvest_strategy(
        is_gmx,
        strategy,
        token,
        gov,
        profit_whale,
        profit_amount,
        target,
    )
    print("Profit:", profit / 1e18)
    # record this here so it isn't affected if we donate via ySwaps
    strategy_assets = strategy.estimatedTotalAssets()

    print(
        "After seventh harvest Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # simulate profits
    chain.sleep(sleep_time)

    # harvest, store new asset amount
    (profit, loss, extra) = harvest_strategy(
        is_gmx,
        strategy,
        token,
        gov,
        profit_whale,
        profit_amount,
        target,
    )
    print("Profit:", profit / 1e18)
    # record this here so it isn't affected if we donate via ySwaps
    strategy_assets = strategy.estimatedTotalAssets()

    print(
        "After eighth harvest Vault assets:",
        vault.totalAssets() / 1e18,
        "Strategy assets",
        strategy.estimatedTotalAssets() / 1e18,
        "Strategy gain",
        vault.strategies(strategy)["totalGain"] / 1e18,
        "Strategy debt",
        vault.strategies(strategy)["totalDebt"] / 1e18,
        "Rewards balance",
        vault.balanceOf(rewards),
        "Share Price",
        vault.pricePerShare() / 1e18,
    )

    # confirm we made money, or at least that we have about the same
    if no_profit:
        assert pytest.approx(new_assets, rel=RELATIVE_APPROX) == old_assets
    else:
        new_assets > old_assets

    # simulate five days of waiting for share price to bump back up
    chain.sleep(86400 * 5)
    chain.mine(1)

    # Display estimated APR
    print(
        "\nEstimated APR: ",
        "{:.2%}".format(
            ((new_assets - old_assets) * (365 * 86400 / sleep_time)) / (strategy_assets)
        ),
    )

    # withdraw and confirm we made money, or at least that we have about the same
    vault.withdraw({"from": whale})
    if no_profit:
        assert (
            pytest.approx(token.balanceOf(whale), rel=RELATIVE_APPROX) == starting_whale
        )
    else:
        assert token.balanceOf(whale) > starting_whale
