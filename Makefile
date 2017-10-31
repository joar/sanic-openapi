SWAGGER_UI_REF ?= master
SWAGGER_UI_TAR_URL := https://github.com/swagger-api/swagger-ui/archive/$(SWAGGER_UI_REF).tar.gz
SWAGGER_UI_DIR := sanic_openapi/ui
SWAGGER_UI_DIST_PATH := swagger-ui-$(SWAGGER_UI_REF)/dist
SWAGGER_UI_EXCLUDE ?= index.html

update-swagger-ui:
	curl --silent -L $(SWAGGER_UI_TAR_URL) \
		| tar \
			--strip-components=2 \
			-C $(SWAGGER_UI_DIR) \
			-vzx \
			--exclude $(SWAGGER_UI_EXCLUDE)
