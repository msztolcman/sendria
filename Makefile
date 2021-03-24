## building
distro: ## build and upload distro
	clean build upload

clean: ## cleanup all distro
	-rm -fr dist
	-rm -fr __pycache__
	-rm -fr sendria/__pycache__
	-rm -fr build
	-rm -fr sendria/static/.webassets-cache/ sendria/static/assets/bundle.*

build: ## build distro
	webassets -m sendria.build_assets build
	python3 setup.py sdist bdist_wheel
	-rm -rf sendria/static/.webassets-cache/ sendria/static/assets/bundle.*

upload: ## upload distro
	twine upload dist/sendria*

upload-test: ## upload distro to test Pypi
	twine upload --repository testpypi dist/sendria*

test: ## run test suite
	pytest --nf --ff -q

lint: ## run external tools like flake8, bandit, safety
	flake8 sendria
	bandit -rq sendria
	safety check --bare

.DEFAULT_GOAL := help
help:
	@grep -E '(^[a-zA-Z_-]+:.*?##.*$$)|(^##)' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}{printf "\033[32m%-30s\033[0m %s\n", $$1, $$2}' | sed -e 's/\[32m##/[33m/'
