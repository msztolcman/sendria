## building
distro: ## build and upload distro
	clean build upload

clean: ## cleanup all distro
	-rm -fr dist
	-rm -fr __pycache__
	-rm -fr mailtrap/__pycache__
	-rm -fr build
	-rm -fr mailtrap/static/.webassets-cache/ mailtrap/static/assets/bundle.*

build: ## build distro
	webassets -m mailtrap.build_assets build
	python3 setup.py sdist bdist_wheel
	-rm -rf mailtrap/static/.webassets-cache/ mailtrap/static/assets/bundle.*

upload: ## upload distro
	twine upload dist/mailtrap*

upload-test: ## upload distro to test Pypi
	twine upload --repository testpypi dist/mailtrap*

.DEFAULT_GOAL := help
help:
	@grep -E '(^[a-zA-Z_-]+:.*?##.*$$)|(^##)' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}{printf "\033[32m%-30s\033[0m %s\n", $$1, $$2}' | sed -e 's/\[32m##/[33m/'
