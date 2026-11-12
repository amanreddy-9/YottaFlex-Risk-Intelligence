.PHONY: generate-starter generate-full verify-repro validate evaluate run-all build-web test serve

SEED ?= 20261022
SCALE ?= full
PORT ?= 8080

generate-starter:
	PYTHONPATH=src python3 -m yottaflex.cli generate --scale starter --seed $(SEED)

generate-full:
	PYTHONPATH=src python3 -m yottaflex.cli generate --scale full --seed $(SEED)

verify-repro:
	PYTHONPATH=src python3 -m yottaflex.cli verify-repro --scale $(SCALE) --seed $(SEED)

validate:
	PYTHONPATH=src python3 -m yottaflex.cli validate --scale $(SCALE)

evaluate:
	PYTHONPATH=src python3 -m yottaflex.cli evaluate --scale $(SCALE)

run-all:
	PYTHONPATH=src python3 -m yottaflex.cli run-all --scale $(SCALE) --seed $(SEED)

build-web:
	npm --prefix web install && npm --prefix web run build

test:
	python3 -m unittest discover -s tests -v

serve:
	PYTHONPATH=src python3 -m yottaflex.cli serve --scale $(SCALE) --port $(PORT)
