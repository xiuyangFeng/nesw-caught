# Market Relevance Morning Report

## Latest Metrics

- precision: `0.8500`
- recall: `1.0000`
- noise_rejection_rate: `0.9286`
- evaluated sample count: `59`

## Benchmark Snapshot

- total benchmark samples: `59`
- market relevant: `17`
- noise samples: `42`

## False Positives

- `historical-0134-134` 8点1氪丨宝宝巴士推送低俗广告被罚30万；山姆客服回应给三文鱼加不可生食标签；360回应“安全龙虾”私钥泄露 | expected: not relevant (low_information)
- `historical-0212-212` 湖北交投建设集团注册资金增至65亿元 | expected: not relevant (off_topic)
- `realtime-0280-1720` 山西省融资再担保集团注册资本增至约39.9亿元 | expected: not relevant (off_topic)

## False Negatives

- (none)

## Recent Experiments

- `2026-03-26T16:16:55.656633Z` `exp-20260327-iran-war-powers` `keep`: Catch Iran war-powers vote headlines without broadening generic Iran politics | precision improved from 0.8421 to 0.8500
- `2026-03-26T10:49:29.550063Z` `exp-20260326-taiwan-arms-sale` `keep`: Catch Taiwan arms-sale headlines without broadening generic geopolitics | precision improved from 0.8333 to 0.8421
- `2026-03-26T06:45:27.360578Z` `exp-20260326-recall-merge` `keep`: Combine concept-mover and shipping-route recall improvements | precision improved from 0.8125 to 0.8333
- `2026-03-25T15:54:47.760062Z` `exp-20260325-index-signals` `keep`: Catch index spikes, commodity price wires, and market stability plans | precision improved from 0.7500 to 0.8125
- `2026-03-25T15:20:27.953701Z` `baseline-20260325-market-relevance-v2` `baseline`: baseline evaluation | precision=0.7500,recall=0.5294,noise_rejection_rate=0.9286,dataset=backend/data/research/market_relevance_benchmark.jsonl,artifacts=backend/data/research/market_relevance_baseline

## Next Read

- 优先看 false negatives，找当前规则漏掉的市场信号。
- 如果 precision 开始下降，先回看最近一条 keep/reject 实验记录。