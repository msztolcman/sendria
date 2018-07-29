distro: clean build upload

init:
	pip install -r requirements.txt

init-dev:
	pip install -r requirements-dev.txt

clean:
	-rm -fr dist
	-rm -fr __pycache__
	-rm -fr mailtrap/__pycache__
	-rm -fr build
	-rm -fr mailtrap/static/.webassets-cache/ mailtrap/static/assets/bundle.*

build:
	webassets -m mailtrap.web 'build'
	webassets -m mailtrap.web 'build' --production
	python3 setup.py sdist bdist_wheel
	-rm -rf mailtrap/static/.webassets-cache/ mailtrap/static/assets/bundle.*

upload:
	twine upload dist/mailtrap*
