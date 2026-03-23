# mac-bench Vision Benchmark

- Ran at: `2026-03-23 17:11:34 UTC`
- Finished at: `2026-03-23 17:14:01 UTC`
- Duration: `0:02:27.083738`
- Machine: `Mac mini` / `Apple M4 Pro` / `64 GB RAM`

## What This Run Tested

- Request profile: `default`
- Temperature: `0.0`
- Max tokens: `160`
- Images: `5`

## Prompt

```text
Describe only the visible person or people in this image in 1 to 2 short sentences. Mention clothing, hats, glasses, masks, shoes, bags, boxes, phones, packages, or other objects they are wearing or carrying. Do not mention the environment, house, porch, background, weather, doorway, camera overlay, or timestamp text unless it is strictly necessary to identify an object on the person. If something is uncertain, say probably or possibly. If no person is visible, reply with exactly: No person visible.
```

## Recommendation

- Recommended result: `mistralai/ministral-3-3b` / `default` at `2.698s` average latency.
- Why: Fastest stable result within the 32 GiB target.
- Lightest stable result: `mistralai/ministral-3-3b` / `default` at `2.78 GiB`.

## Charts

### Speed vs Memory

```mermaid
quadrantChart
    title Speed vs memory footprint
    x-axis Slow --> Fast
    y-axis Low RAM --> High RAM
    quadrant-1 Fast but heavy
    quadrant-2 Best zone
    quadrant-3 Light but slower
    quadrant-4 Heavy and slower
    "mistralai/ministral-3-3b [default]": [1.000, 0.000]
    "allenai/olmocr-2-7b [default]": [0.659, 0.855]
    "qwen/qwen2.5-vl-7b [default]": [0.569, 0.855]
    "qwen/qwen3.5-9b [default]": [0.000, 1.000]
```

### Average Latency

```mermaid
xychart-beta
    title "Average image latency by result"
    x-axis ["mistralai/ministral-3-3b [default]", "allenai/olmocr-2-7b [default]", "qwen/qwen2.5-vl-7b [default]", "qwen/qwen3.5-9b [default]"]
    y-axis "Seconds" 0 --> 9.05
    bar [2.698, 4.525, 5.005, 8.051]
```

## Summary

| Model | Profile | Format | Load RAM GiB | Avg s | Median s | Tok/s | Success | Reasoning |
|---|---|---|---:|---:|---:|---:|---:|---|
| `mistralai/ministral-3-3b` | `default` | `gguf` | 2.780 | 2.698 | 2.746 | 14.976 | 5/5 | no |
| `allenai/olmocr-2-7b` | `default` | `gguf` | 5.620 | 4.525 | 4.593 | 4.641 | 4/5 | no |
| `qwen/qwen2.5-vl-7b` | `default` | `gguf` | 5.620 | 5.005 | 5.187 | 4.745 | 4/5 | no |
| `qwen/qwen3.5-9b` | `default` | `gguf` | 6.100 | 8.051 | 8.051 | 16.395 | 1/5 | yes |
| `qwen/qwen3.5-35b-a3b` | `default` | `gguf` | 20.560 | - | - | - | 0/5 | no |

## Excluded Installed Models

- `qwen/qwen3-vl-8b`: not selected
- `mistralai/devstral-small-2-2512`: not selected
- `nvidia/nemotron-3-nano`: not vision-capable
- `qwen/qwen3-vl-4b`: not selected
- `zai-org/glm-4.7-flash`: not vision-capable
- `zai-org/glm-4.6v-flash`: not selected
- `meta-llama-3.1-8b-instruct-hf`: not vision-capable

## Images

- `01-doorbell-takeout.jpg`: Daytime courier pressing the doorbell with a parcel
- `02-knock-packages.jpg`: Dusk food delivery at the front door
- `03-front-door-dropoff.jpg`: Partial courier frame while leaving parcels on the mat
- `04-delivering-takeout.jpg`: Night delivery driver carrying parcels under the porch light
- `05-online-order-dropoff.jpg`: Empty porch after a delivery with no person visible

## Ministral 3 3B / default

- Model key: `mistralai/ministral-3-3b`
- Identifier used for API: `bench-mistralai-ministral-3-3b`
- Format: `gguf`
- Variant: `mistralai/ministral-3-3b@q4_k_m`
- Params: `3B`
- Estimated total memory: `3.01 GiB`
- Reported load memory: `2.78 GiB`
- Load time: `1.64s`
- Average image latency: `2.698s`
- Median image latency: `2.746s`
- Completion throughput: `14.976 tokens/s`
- Success rate: `5/5`

| Image | Time s | Prompt Tokens | Completion Tokens | Reasoning | Response |
|---|---:|---:|---:|---|---|
| `01-doorbell-takeout.jpg` | 3.262 | 1656 | 44 | no | A man in a dark gray hooded jacket and black gloves is holding a wooden box labeled "UPS" near his body while opening a door. He wears a black cap and appears to be wearing sneakers. |
| `02-knock-packages.jpg` | 2.547 | 1656 | 43 | no | The individual in the image is wearing a dark hooded jacket, a black cap, and appears to be holding a smartphone while standing near an open door. They have a brown paper bag hanging from one hand. |
| `03-front-door-dropoff.jpg` | 2.746 | 1656 | 55 | no | A person in a dark long-sleeved shirt and rolled-up pants is carrying two stacked cardboard boxes while wearing sneakers. The upper body is not fully visible, but there are no hats, glasses, masks, bags, phones, or packages clearly attached to them. |
| `04-delivering-takeout.jpg` | 2.771 | 1656 | 55 | no | A person in a dark jacket, light-colored reflective vest, and brown pants stands holding what appears to be a clipboard or document. They are wearing a white cap and possibly black shoes; they do not have any visible bags, masks, glasses, phones, or packages. |
| `05-online-order-dropoff.jpg` | 2.162 | 1656 | 5 | no | No person visible. |

## Olmocr 2 7B / default

- Model key: `allenai/olmocr-2-7b`
- Identifier used for API: `bench-allenai-olmocr-2-7b`
- Format: `gguf`
- Variant: `allenai/olmocr-2-7b@q4_k_m`
- Params: `7B`
- Estimated total memory: `5.90 GiB`
- Reported load memory: `5.62 GiB`
- Average image latency: `4.525s`
- Median image latency: `4.593s`
- Completion throughput: `4.641 tokens/s`
- Success rate: `4/5`

| Image | Time s | Prompt Tokens | Completion Tokens | Reasoning | Response |
|---|---:|---:|---:|---|---|
| `01-doorbell-takeout.jpg` | 4.535 | 1278 | 18 | no | A man in a dark jacket and gloves is opening a door while holding a package. |
| `02-knock-packages.jpg` | 4.651 | 1278 | 24 | no | A person wearing a dark jacket, hat, and possibly a mask is holding a phone and a brown paper bag. |
| `03-front-door-dropoff.jpg` | 4.913 | 1278 | 37 | no | A man is bending over, placing a cardboard box on top of another box on a porch. He is wearing a dark long-sleeve shirt, cargo pants, and sneakers. |
| `04-delivering-takeout.jpg` | 1.675 | - | - | no | ERROR: HTTP 400 from http://127.0.0.1:1234/v1/chat/completions: {"error":"failed to process image"} |
| `05-online-order-dropoff.jpg` | 4.001 | 1278 | 5 | no | No person visible. |

## Qwen2.5 VL 7B / default

- Model key: `qwen/qwen2.5-vl-7b`
- Identifier used for API: `bench-qwen-qwen2-5-vl-7b`
- Format: `gguf`
- Variant: `qwen/qwen2.5-vl-7b@q4_k_m`
- Params: `7B`
- Estimated total memory: `5.90 GiB`
- Reported load memory: `5.62 GiB`
- Average image latency: `5.005s`
- Median image latency: `5.187s`
- Completion throughput: `4.745 tokens/s`
- Success rate: `4/5`

| Image | Time s | Prompt Tokens | Completion Tokens | Reasoning | Response |
|---|---:|---:|---:|---|---|
| `01-doorbell-takeout.jpg` | 5.260 | 1278 | 34 | no | A man wearing a dark hoodie and gloves holds a package in his left hand while opening a door with his right hand. He appears to be delivering mail or packages. |
| `02-knock-packages.jpg` | 5.128 | 1278 | 25 | no | A person wearing a dark jacket and hat holds a phone in one hand while carrying a brown paper bag in the other. |
| `03-front-door-dropoff.jpg` | 5.246 | 1278 | 31 | no | A man wearing a dark hoodie and camouflage pants is bending over to place two cardboard boxes on a doormat. He appears to be wearing sneakers. |
| `04-delivering-takeout.jpg` | 1.795 | - | - | no | ERROR: HTTP 400 from http://127.0.0.1:1234/v1/chat/completions: {"error":"failed to process image"} |
| `05-online-order-dropoff.jpg` | 4.386 | 1278 | 5 | no | No person visible. |

## Qwen3.5 9B / default

- Model key: `qwen/qwen3.5-9b`
- Identifier used for API: `bench-qwen-qwen3-5-9b`
- Format: `gguf`
- Variant: `qwen/qwen3.5-9b@q4_k_m`
- Params: `9B`
- Estimated total memory: `6.85 GiB`
- Reported load memory: `6.10 GiB`
- Load time: `3.67s`
- Average image latency: `8.051s`
- Median image latency: `8.051s`
- Completion throughput: `16.395 tokens/s`
- Success rate: `1/5`

| Image | Time s | Prompt Tokens | Completion Tokens | Reasoning | Response |
|---|---:|---:|---:|---|---|
| `01-doorbell-takeout.jpg` | 8.351 | 999 | 160 | yes | ERROR: Blank final response. |
| `02-knock-packages.jpg` | 8.769 | 999 | 160 | yes | ERROR: Blank final response. |
| `03-front-door-dropoff.jpg` | 8.778 | 999 | 160 | yes | ERROR: Blank final response. |
| `04-delivering-takeout.jpg` | 8.888 | 999 | 160 | yes | ERROR: Blank final response. |
| `05-online-order-dropoff.jpg` | 8.051 | 999 | 132 | yes | No person visible. |

## Qwen3.5 35B A3B / default

- Model key: `qwen/qwen3.5-35b-a3b`
- Identifier used for API: `bench-qwen-qwen3-5-35b-a3b`
- Format: `gguf`
- Variant: `qwen/qwen3.5-35b-a3b@q4_k_m`
- Params: `35B-A3B`
- Estimated total memory: `21.25 GiB`
- Reported load memory: `20.56 GiB`
- Load time: `9.04s`
- Success rate: `0/5`

| Image | Time s | Prompt Tokens | Completion Tokens | Reasoning | Response |
|---|---:|---:|---:|---|---|
| `01-doorbell-takeout.jpg` | 6.051 | 999 | 160 | yes | ERROR: Blank final response. |
| `02-knock-packages.jpg` | 6.007 | 999 | 160 | yes | ERROR: Blank final response. |
| `03-front-door-dropoff.jpg` | 6.045 | 999 | 160 | yes | ERROR: Blank final response. |
| `04-delivering-takeout.jpg` | 6.099 | 999 | 160 | yes | ERROR: Blank final response. |
| `05-online-order-dropoff.jpg` | 6.034 | 999 | 160 | yes | ERROR: Blank final response. |
