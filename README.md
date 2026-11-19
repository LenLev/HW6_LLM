# HW6: ускорение инференса

## Результаты

- Qwen3-8B на GPU A100 80 GB.
- При 120 RPM конфигурация с EAGLE-3 дала среднюю задержку **4,89 с** против **6,90 с** у baseline — ускорение **1,41x**.
- Проверенный максимум нагрузки с выполнением SLA P90 < 15 с: **200 RPM**.
- При 210 RPM P90 достигла 16,89 с.
- До 180 RPM EAGLE-3 ускоряет инференс; при 240 RPM он уже проигрывает baseline.

## Артефакты

- Конфигурации сервера: [configs/](configs/)
- Скрипты запуска: [benchmark.sh](benchmark.sh), [sweep.sh](sweep.sh), [load_test.sh](load_test.sh)
- Таблицы:
  - [configurations.csv](tables/configurations.csv) — сравнение конфигураций
  - [speculation.csv](tables/speculation.csv) — эффект спекулятивного декодирования по нагрузке
  - [load_test.csv](tables/load_test.csv) — проверка пропускной способности и SLA
- Графики: [figures/speculation.png](figures/speculation.png), [figures/capacity.png](figures/capacity.png)
- Отчет: [report.pdf](report.pdf) и [report.md](report.md)
- Исходные данные и результаты: [data/requests.jsonl](data/requests.jsonl), [results/](results/)

## Методика

- Модель: `Qwen/Qwen3-8B`, без thinking, `temperature=0`, `seed=42`, `max_tokens=512`.
- Тесты проводились через AIPerf с тем же набором из 640 запросов.
- Перед тестами очищался prefix cache.
- Метрики: средняя и P90 end-to-end latency.
- Нагрузочный тест длился 300 секунд при постоянном request rate.

## Повторный запуск

```bash
sudo docker build -t hw6-lena:20261119 .
sudo docker run -d --name hw6-lena-20261119 --gpus device=1 --ipc=host \
  -p 127.0.0.1:18061:8000 -e HF_HOME=/cache \
  -v rlvr-hf-cache:/cache -v "$PWD":/homework hw6-lena:20261119 sleep infinity
sudo python3 run_experiments.py --configs baseline chunk2048 chunk1024 eagle3
```
