.PHONY: up down build logs backend-shell frontend-shell db-shell test

up:
	docker-compose up -d

down:
	docker-compose down

build:
	docker-compose build

logs:
	docker-compose logs -f

backend-shell:
	docker-compose exec backend bash

frontend-shell:
	docker-compose exec frontend bash

db-shell:
	docker-compose exec db psql -U user -d flashflood

test:
	docker-compose exec backend pytest
