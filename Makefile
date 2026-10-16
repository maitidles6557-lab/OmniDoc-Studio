.DEFAULT_GOAL := help
.PHONY: help install test coverage lint run docker clean

help:  ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install:  ## Install runtime and dev dependencies
	pip install -r requirements-dev.txt

test:  ## Run the offline unit tests
	python -m unittest discover -s tests -t . -v

coverage:  ## Run tests with a coverage report
	python -m coverage run -m unittest discover -s tests -t .
	python -m coverage report

lint:  ## Lint with ruff
	ruff check .

run:  ## Start the Streamlit app
	streamlit run app.py

docker:  ## Build the Docker image
	docker build -t omnidoc-studio .

clean:  ## Remove caches and coverage artifacts
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
	rm -rf .pytest_cache .ruff_cache .coverage htmlcov
