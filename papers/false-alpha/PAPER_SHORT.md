# More Strategies, Same Zero
**Does machine scale strategy search find real edge, or manufacture false discoveries?**

*Parv Mehndiratta. Short working paper. Every number comes from a committed, seeded script (github.com/0103-parv/mentat).*

**In one line.** When an AI invents and backtests trading strategies by the thousand, the best one always looks impressive and almost none of it is real, and the correction that catches the fakes also makes any modest genuine edge impossible to prove.

## The trap

A backtest grades a strategy on the past, and the more strategies you try, the more sure you can be that the best one was lucky rather than good. In one form this is old news. Bailey and Lopez de Prado showed that even under pure chance, the best Sharpe out of N tries climbs steadily with N, so a large enough search always turns up something that looks brilliant. What is new is that a language model can run that search for almost nothing. It will propose ten strategies, then a hundred, then three thousand, tirelessly. So the question stops being academic. Point an AI at the market and let it discover strategies, and do the genuinely profitable ones pile up, or do you only manufacture a growing pile of convincing mirages?

## The test

I built a small trading engine whose one interesting feature is a deliberately brutal test that every strategy has to pass. A strategy earns a return only on information it held before the trade, it pays realistic transaction costs on every change of position, it is judged by its worst stretch across several separate out of sample periods rather than its average, and its score is then docked by exactly the amount the best of N would be expected to earn under pure luck. Then I turn one dial, the number of strategies, from ten up to three thousand. Three proposers take turns feeding the engine, a plain random generator, an evolutionary one, and a live language model actually inventing the strategies, and I run all of it on seven real markets, from the S&P 500 to gold, currencies, and Bitcoin. To make sure the test itself can be trusted, I also run it on a fake market with a real pattern secretly planted inside, and on a market that is pure noise.

## The result

**The naive view gets fooled, and worse as the search grows.** On pure noise the best strategy climbs to a Sharpe near 0.35, and on the real S&P 500 it reaches about 1.0, a number most people would happily trade. Hundreds of strategies look like winners.

**The honest test holds the line at exactly zero.** Across thousands of strategies, on all seven real markets, at every search size, for all three proposers including the live AI, not one survives. And this is not a test that simply says no to everything. On the planted market, where a real edge exists, the same test passes strategies, and passes more of them as the search grows. So zero is a real answer, not a broken one.

**Searching harder backfires, and this is the part I find sharpest.** Every time you try more strategies, the bar for proving any of them real rises faster than the search finds edge. A genuine edge the test accepts after ten tries is rejected after thirty, because you raised your own bar past it. By a thousand strategies a strategy needs a true worst period Sharpe well above one just to be provable, and the best any real market here offers is around 0.85. So the honest conclusion is not that these markets are efficient. It is that no edge large enough to prove, after a search this aggressive, is there to be found.

One thing worth adding: the AI did not help. The creative and live language model proposers produced more original looking winners than random search, but converted exactly zero of them into survivors, and amplified a real edge only when one was genuinely present. The creativity is in the inventing. The honesty has to come from the test.

## What is genuinely new, and what is not

I want to be precise, because most of the machinery here is borrowed, and I think saying so plainly is a strength rather than a weakness. The finding that AI trading edge evaporates under a serious evaluation is already established, and the core statistics are Bailey and Lopez de Prado's and White's, not mine. My own contributions are smaller and specific:

- The standard luck correction was derived for a single Sharpe, but my test scores a strategy by its worst period, which has a thinner tail. I derive the correction that statistic actually needs, show the usual one is about 2.4 times too harsh, and find the zero survives even after loosening it to the correct bar.
- I show why the tempting analytic shortcuts fail. About 78 percent of what separates the best strategy from the rest is structural, a genuinely different strategy, not a luckier estimate of the same one, so the clean formulas do not apply and only a resampling test settles it.
- I find that a language model runs out of genuinely distinct ideas quickly, giving only 160 different strategies out of a thousand tries.

## What it does not show

The zero is a statement about precision, not about the market. By design the test misses any edge below a fairly high bar, so zero survivors always means no edge provable at this scale, never no edge exists. The strategy language is small and the data is daily, and a richer space might surface a survivor. Even a survivor would be provisional, since markets do not sit still. The result that carries beyond finance is the method, not the particular answer: run any generate and test loop under a fixed true effect and a growing number of tries, and the same trap appears.
