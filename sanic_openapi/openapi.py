import logging
import json
import re
from itertools import repeat
from typing import Optional, Callable, Dict, List, Tuple, Set

from sanic.blueprints import Blueprint
import sanic.response
from sanic.views import CompositionView

import openapilib.helpers
from openapilib import spec, serialize_spec
from .doc import route_specs

_log = logging.getLogger(__name__)

blueprint = Blueprint('openapi', url_prefix='openapi')

_SPEC = {}


HANDLER_SPEC_ATTRIBUTE = 'operation_spec'


# Removes all null values from a dictionary
def remove_nulls(dictionary, deep=True):
    return {
        k: remove_nulls(v, deep) if deep and type(v) is dict else v
        for k, v in dictionary.items()
        if v is not None
    }


@blueprint.listener('before_server_start')
def build_spec(app, loop=None):
    # --------------------------------------------------------------- #
    # Blueprint Tags
    # --------------------------------------------------------------- #

    for blueprint in app.blueprints.values():
        if hasattr(blueprint, 'routes'):
            for route in blueprint.routes:
                route_spec = route_specs[route.handler]
                route_spec.blueprint = blueprint
                if not route_spec.tags:
                    route_spec.tags.append(blueprint.name)

    path_spec, seen_tags = build_path_spec(app)

    contact_spec = spec.SKIP
    contact_email = getattr(app.config, 'API_CONTACT_EMAIL', spec.SKIP)
    if contact_email is not spec.SKIP:
        contact_spec = spec.Contact(
            email=contact_email
        )

    license_spec = spec.SKIP
    license_name = getattr(app.config, 'API_LICENSE_NAME', spec.SKIP)
    license_url = getattr(app.config, 'API_LICENSE_URL', spec.SKIP)

    if any(i is not spec.SKIP for i in (license_name, license_url)):
        license_spec = spec.License(
            name=license_name,
            url=license_url,
        )

    api_spec = spec.OpenAPI(
        info=spec.Info(
            version=getattr(app.config, 'API_VERSION', '1.0.0'),
            title=getattr(app.config, 'API_TITLE', 'API'),
            description=getattr(app.config, 'API_DESCRIPTION', ''),
            terms_of_service=getattr(app.config, 'API_TERMS_OF_SERVICE',
                                     spec.SKIP),
            contact=contact_spec,
            license=license_spec,
        ),
        paths=path_spec,
        components=spec.Components(),
        # tags=[{'name': name} for name in seen_tags]
    )

    _SPEC.update(
        serialize_spec(api_spec)
    )
    _log.debug(
        'api_spec:%s', openapilib.helpers.LazyString(
            lambda: '\n' + json.dumps(
                serialize_spec(api_spec),
                indent=2
            )
        )
    )
    return _SPEC


def build_path_spec(
        app
) -> Tuple[
    Dict[str, spec.PathItem],
    Set[str]
]:
    paths = {}
    seen_tags = set()

    blueprint_handler_tags: Dict[Callable, Set[str]] = {}

    for blueprint in app.blueprints.values():
        if hasattr(blueprint, 'routes'):
            for route in blueprint.routes:
                blueprint_handler_tags.setdefault(route.handler, set()).add(
                    blueprint.name)

    _log.debug(
        'blueprint_handler_tags:%s',
        openapilib.helpers.LazyPretty(
            lambda: {repr(k): list(v) for k, v in
                     blueprint_handler_tags.items()}
        )
    )

    for uri, route in app.router.routes_all.items():
        if uri.startswith("/swagger") or uri.startswith("/openapi") \
                or '<file_uri' in uri:
            # TODO: add static flag in sanic routes
            continue

        # --------------------------------------------------------------- #
        # Methods
        # --------------------------------------------------------------- #

        # Build list of methods and their handler functions
        handler_type = type(route.handler)
        if handler_type is CompositionView:
            view = route.handler
            method_handlers = view.handlers.items()
        else:
            method_handlers = zip(route.methods, repeat(route.handler))

        path_item_kwargs: Dict[str, spec.Operation] = {}

        for method, handler in method_handlers:
            operation_spec: Optional[spec.Operation] = getattr(
                handler,
                HANDLER_SPEC_ATTRIBUTE,
                None
            )
            if operation_spec is None:
                continue

            path_item_kwargs[method.lower()] = operation_spec

            if operation_spec.tags is spec.SKIP:
                # Add blueprint tag
                _log.debug('%r %r', handler, handler in blueprint_handler_tags)
                if handler in blueprint_handler_tags:
                    operation_spec.add_tags(*blueprint_handler_tags[handler])
            elif isinstance(operation_spec.tags, (list, set)):
                seen_tags |= set(operation_spec.tags)

            parameters: List[spec.Parameter] = []

            for route_parameter in route.parameters:
                parameters.append(
                    spec.Parameter(
                        name=route_parameter.name,
                        in_=spec.ParameterLocation.PATH,
                        required=True,
                        schema=spec.Schema.from_type(route_parameter.cast)
                    )
                )

            operation_spec.parameters = parameters

        uri_parsed = uri
        for route_parameter in route.parameters:
            uri_parsed = re.sub('<' + route_parameter.name + '.*?>',
                                '{' + route_parameter.name + '}', uri_parsed)

        paths[uri_parsed] = spec.PathItem(**path_item_kwargs)

    return paths, seen_tags


@blueprint.route('/spec.json')
def get_spec(request):
    return sanic.response.json(_SPEC)
