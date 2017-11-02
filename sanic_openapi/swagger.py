import os

from sanic import response
from sanic.blueprints import Blueprint
from sanic.request import Request

dir_path = os.path.dirname(os.path.realpath(__file__))
dir_path = os.path.abspath(dir_path + '/ui')

blueprint = Blueprint('swagger', url_prefix='swagger', strict_slashes=True)

blueprint.static('/', dir_path + '/index.html')
blueprint.static('/', dir_path)


@blueprint.get('')
def redirect_slash(request: Request):
    return response.redirect(request.path + '/')


