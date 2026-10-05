# Set the default goal so running `make` with no arguments prints the help menu

.DEFAULT_GOAL := help
environment := DS2

.PHONY: help
help: ## Show this help menu
	@awk 'BEGIN {FS = ":.*?## "} /^[0-9a-zA-Z_-]+:.*?## / {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)
# ###############################################################33
.PHONY: DS2_load
DS2_load: ## removes Februay data from previous modules
	psql -U luicasad -d piscineds -h localhost -c "DROP TABLE IF EXISTS data_2022_oct; DROP TABLE IF EXISTS data_2022_nov; DROP TABLE IF EXISTS data_2022_dec; DROP TABLE IF EXISTS data_2023_jan; DROP TABLE IF EXISTS items;"


.PHONY: DS2_ex00
DS2_ex00: ## Pie chart to understand what people do on the site
	python ex00/pie.py

.PHONY: DS2_ex01
DS2_ex01: ## Customers by day, sales by month, Averaga customer expenidure by day
	python ex01/chart.py

.PHONY: DS2_ex02
DS2_ex02: ## Basic statiscis for items purchased, average basket price per user
	python ex02/mustache.py

.PHONY: DS2_ex03
DS2_ex03: ## Histograms for Frecuency and spent
	python ex03/Building.py

.PHONY: DS2_ex04
DS2_ex04: ## Find optimal number of clusters
	python ex04/elbow.py

.PHONY: DS2_ex05
DS2_ex05: ## Plot clusters
	python ex05/Clustering.py
# ###############################################################33

.PHONY: set
set: ## Set a python environment for this project
	sh -c "python3 -m venv $(environment) && source $(environment)/bin/activate && pip install --upgrade pip &&pip install -r requirements.txt"

.PHONY: activate
activate: ## Activate the python environment for this project
	@echo "Run: source ../$(environment)/bin/activate"

.PHONY: deactivate
deactivate: ## Deactivate the python environment for this project
	deactivate

.PHONY: unset
unset: ## removes the python 
	rm -rf $(environment)

.PHONY: upgrade
upgrade: ## Upgrades pip
	pip install --upgrade pip

.PHONY: norminette
norminette: ## Run norminette on all .py files
	flake8  */*.py		

.PHONY: entrega
entrega: ## copies deliverable files to 42 repo
	mkdir ../../DS0/ex00
	mkdir ../../DS0/ex02
	mkdir ../../DS0/ex03
	mkdir ../../DS0/ex04
	cp ex00/VM-instructions.md ../../DS0/ex00/
	cp ex02/table.py ../../DS0/ex02/
	cp ex03/automatic_table.py ../../DS0/ex03/
	cp ex04/items_table.py ../../DS0/ex04/
	cp Makefile ../../DS0
	cp requirements.txt ../../DS0

.PHONY: drop
drop: ## Drops items and data_202*_*** tables
	psql -U luicasad -d piscineds -h localhost -c "DROP TABLE IF EXISTS data_2022_oct; DROP TABLE IF EXISTS data_2022_nov; DROP TABLE IF EXISTS data_2022_dec; DROP TABLE IF EXISTS data_2023_jan; DROP TABLE IF EXISTS items;"

