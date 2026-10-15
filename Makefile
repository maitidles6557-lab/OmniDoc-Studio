.PHONY: install test lint run docker
install:
	pip install -r requirements-dev.txt
test:
	python -m unittest discover -s tests -t . -v
lint:
	ruff check .
run:
	streamlit run app.py
docker:
	docker build -t omnidoc-studio .
