# SafeLens: Hateful Video Moderation

## Demo Video

- [YouTube](https://youtu.be/B1dYceLSnXA)

## Repo Guide


**Repo Layout**

- `web/` — Website/UI for the demo and docs. Everything related to the web frontend shown in the video demo lives here.
- `auth-service/` — Authentication service (API and logic). Everything related to auth lives here. (required to setup the web demo)

**Project Tree**

```
.
├── web/               # Website/UI (backend & frontend)
│   ├── frontend/      # frontend
│   └── ...            # backend
├── auth-service/      # Authentication service
│   ├── src/
│   └── ...
├── README.md
```

## Setup

1. Setup `auth-service/` by following `auth-service/README.md`
1. Setup `web/` by following `web/README.md` and `web/frontend/README.md`

## Evaluation

We benchmarked multiple policy LLMs and vision–language (VL) back ends on **19 videos** (~**10%** of the training data) using two complementary perspectives:  
- **Duration-weighted (time micro-average):** emphasizes longer harmful spans.  
- **Segment-level (count micro-average):** treats each segment equally.  

Ground truth: **1,593 s harmful of 4,400 s total (~36.2%)**; **183 harmful segments of 530 (~34.5%)**.

---

### Table 1. Duration-weighted results (time micro-average)

| Model (VL + Policy LLM)              |  TP  |  TN  |  FP  |  FN  | Harmful Duration (s) | Total Duration (s) | F1 Score | Precision | Recall |
|--------------------------------------|-----:|-----:|-----:|-----:|---------------------:|-------------------:|:--------:|:---------:|:------:|
| Qwen2.5-VL + DeepSeek-R1             |  652 | 2331 |  476 |  941 |                1593  |              4400  | **47.90%** | 57.80% | 40.90% |
| Qwen2.5-VL + Llama-3.3-8B-Instruct   |  651 | 2300 |  507 |  942 |                1593  |              4400  | 47.34% | 56.20% | 40.90% |
| Qwen2.5-VL + GPT-5                   |  670 | 2194 |  613 |  923 |                1593  |              4400  | 46.59% | 52.22% | **42.06%** |
| BLIP-2 + class classifier + GPT-5    |  583 | 2458 |  349 | 1010 |                1593  |              4400  | 46.19% | 62.60% | 36.60% |
| BLIP-2 + GPT-5                       |  573 | 2442 |  365 | 1020 |                1593  |              4400  | 45.31% | 61.10% | 36.00% |
| Qwen2.5-VL + Gemini-2.5-Flash        |  552 | 2413 |  394 | 1041 |                1593  |              4400  | 43.53% | 58.40% | 34.70% |
| Qwen2.5-VL + Qwen2.5-7B-Instruct     |  378 | 2663 |  144 | 1215 |                1593  |              4400  | 35.71% | **72.40%** | 23.70% |
| **Our finetuned Llama-3-8B**                | 760 |  271 | 2157 | 650 | 1593 | 4400 | **50.62%** | 53.90% | **47.71%** |

---

### Table 2. Segment-level results (count micro-average)

| Model (VL + Policy LLM)              |  TP  |  TN  |  FP  |  FN  | Total Harmful Segments | Total Segments | F1 Score | Precision | Recall |
|--------------------------------------|-----:|-----:|-----:|-----:|-----------------------:|---------------:|:--------:|:---------:|:------:|
| Qwen2.5-VL + DeepSeek-R1             |   72 |  289 |   58 |  111 |                   183  |            530 | 46.00% | 55.38% | 39.34% |
| Qwen2.5-VL + Llama-3.3-8B-Instruct   |   72 |  282 |   65 |  111 |                   183  |            530 | 45.00% | 52.55% | 39.34% |
| Qwen2.5-VL + GPT-5                   |   77 |  278 |   69 |  106 |                   183  |            530 | **46.81%** | 52.74% | **42.08%** |
| BLIP-2 + class classifier + GPT-5    |   64 |  306 |   41 |  119 |                   183  |            530 | 44.44% | 60.95% | 34.97% |
| BLIP-2 + GPT-5                       |   63 |  302 |   45 |  120 |                   183  |            530 | 43.30% | 58.33% | 34.43% |
| Qwen2.5-VL + Gemini-2.5-Flash        |   59 |  303 |   44 |  124 |                   183  |            530 | 41.26% | 57.29% | 32.24% |
| Qwen2.5-VL + Qwen2.5-7B-Instruct     |   39 |  329 |   18 |  144 |                   183  |            530 | 32.50% | **68.42%** | 21.31% |
| **Our finetuned Llama-3-8B** | 83 | 271| 76 | 100 | 183 | 530 | **48.54%** | 52.20% | **45.35%** |

---

### Key Takeaways
- **Our finetuned Llama-3-8B** achieves the best **F1 score** at both duration and segment levels.  
- It also delivers the **highest recall** (+5–6% absolute improvement), capturing more harmful content.  
- Precision remains competitive, slightly lower than the highest-precision baseline (Qwen2.5-7B-Instruct).  
- Overall, our model provides the best balance between precision and recall for harmful video detection.  

