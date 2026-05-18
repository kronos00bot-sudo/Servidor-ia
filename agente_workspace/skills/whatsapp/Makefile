.PHONY: install test run infra webhook

install:
	python3 -m pip install -r requirements.txt
	python3 -m pip install -r requirements-dev.txt

test:
	python3 -m pytest -q tests

run:
	python3 -m skills.whatsapp.whatsapp_skill

infra:
	python3 -m skills.whatsapp.utils.infrastructure

webhook:
	python3 -m skills.whatsapp.webhook.endpoint
