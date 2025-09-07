# Docker Compose file
COMPOSE_FILE = docker-compose.yml

.PHONY: help
help:
	@echo "Available commands:"
	@echo "  build      - Build all services (jenkins + streamlit)"
	@echo "  up         - Start all services"
	@echo "  down       - Stop all services"
	@echo "  restart    - Restart all services"
	@echo "  logs       - Show logs for all services"
	@echo "  status     - Check status of all services"
	@echo "  clean      - Remove all services and volumes"
	@echo "  dev        - Build and start all services"
	@echo ""
	@echo "Individual service commands:"
	@echo "  jenkins-build    - Build only Jenkins"
	@echo "  jenkins-up       - Start only Jenkins"
	@echo "  jenkins-logs     - Show Jenkins logs"
	@echo "  streamlit-build  - Build only Streamlit"
	@echo "  streamlit-up     - Start only Streamlit"
	@echo "  streamlit-logs   - Show Streamlit logs"
	@echo "  jupyter-build    - Build only Jupyter"
	@echo "  jupyter-up       - Start only Jupyter"
	@echo "  jupyter-logs     - Show Jupyter logs"

# Build all services
.PHONY: build
build:
	docker compose -f $(COMPOSE_FILE) build

# Start all services
.PHONY: up
up:
	docker compose -f $(COMPOSE_FILE) up -d

# Stop all services
.PHONY: down
down:
	docker compose -f $(COMPOSE_FILE) down

# Restart all services
.PHONY: restart
restart:
	docker compose -f $(COMPOSE_FILE) restart

# Show logs for all services
.PHONY: logs
logs:
	docker compose -f $(COMPOSE_FILE) logs -f

# Check status
.PHONY: status
status:
	docker compose -f $(COMPOSE_FILE) ps

# Clean up
.PHONY: clean
clean:
	docker compose -f $(COMPOSE_FILE) down -v --remove-orphans

# Development: build and start all
.PHONY: dev
dev:
	docker compose -f $(COMPOSE_FILE) up -d --build --wait
	sleep 30
	docker compose exec -T db sh -lc 'mysql -u misp -pexample -h 127.0.0.1 misp -N -s -e "select authkey from users where email = \"admin@admin.test\";" > /tmp/authkey.txt'
	docker compose cp db:/tmp/authkey.txt ./shared/authkey.txt

# Individual Jenkins commands
.PHONY: jenkins-build jenkins-up jenkins-down jenkins-logs jenkins-shell
jenkins-build:
	docker compose -f $(COMPOSE_FILE) build jenkins

jenkins-up:
	docker compose -f $(COMPOSE_FILE) up -d jenkins

jenkins-down:
	docker compose -f $(COMPOSE_FILE) stop jenkins

jenkins-logs:
	docker compose -f $(COMPOSE_FILE) logs -f jenkins

jenkins-shell:
	docker compose -f $(COMPOSE_FILE) exec jenkins /bin/bash

# Individual Streamlit commands
.PHONY: streamlit-build streamlit-up streamlit-down streamlit-logs streamlit-shell
streamlit-build:
	docker compose -f $(COMPOSE_FILE) build streamlit

streamlit-up:
	docker compose -f $(COMPOSE_FILE) up -d streamlit

streamlit-down:
	docker compose -f $(COMPOSE_FILE) stop streamlit

streamlit-logs:
	docker compose -f $(COMPOSE_FILE) logs -f streamlit

streamlit-shell:
	docker compose -f $(COMPOSE_FILE) exec streamlit /bin/bash

.PHONY: jupyter-build jupyter-up jupyter-down jupyter-logs jupyter-shell
jupyter-build:
	docker compose -f $(COMPOSE_FILE) build jupyter

jupyter-up:
	docker compose -f $(COMPOSE_FILE) up -d jupyter

jupyter-down:
	docker compose -f $(COMPOSE_FILE) stop jupyter

jupyter-logs:
	docker compose -f $(COMPOSE_FILE) logs -f jupyter

jupyter-shell:
	docker compose -f $(COMPOSE_FILE) exec jupyter /bin/bash