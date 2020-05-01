from aiohttp import web
from aiohttp_jinja2 import template

from app.service.auth_svc import check_authorization
from app.utility.base_service import BaseService


class GameboardApi(BaseService):

    def __init__(self, services):
        self.auth_svc = services.get('auth_svc')
        self.data_svc = services.get('data_svc')

    @check_authorization
    @template('gameboard.html')
    async def splash(self, request):
        red_ops = [red.display for red in await self.data_svc.locate('operations', dict(access=self.Access.RED))]
        blue_ops = [blue.display for blue in await self.data_svc.locate('operations', dict(access=self.Access.BLUE))]
        return dict(red_ops=red_ops, blue_ops=blue_ops)

    @check_authorization
    async def get_pieces(self, request):
        data = dict(await request.json())
        red_op = await self.data_svc.locate('operations', dict(id=data.get('red')))
        blue_op = await self.data_svc.locate('operations', dict(id=data.get('blue')))
        access = await self.auth_svc.get_permissions(request)
        response = dict(access="blue" if self.Access.BLUE in access else "red",
                        red_op=red_op[0].display if red_op else None,
                        blue_op=blue_op[0].display if blue_op else None,
                        exchanges=self._get_exchanges(red_op, blue_op))
        return web.json_response(response)

    def _get_exchanges(self, red_ops, blue_ops):
        exchanges = dict()
        red_links = sorted([link for op in red_ops for link in op.chain if link.finish and link.cleanup == 0], key=lambda i: i.finish)
        blue_links = sorted([link for op in blue_ops for link in op.chain if link.finish and link.cleanup == 0], key=lambda i: i.finish)
        for link in red_links:
            if link.pid in exchanges.keys():
                exchanges[link.pid]['red'].append(link.display)
            else:
                exchanges[link.pid] = dict(red=[link.display], blue=[])
        if blue_ops and 'Auto-Collect' not in blue_ops[0].name:
            self._set_pins(blue_ops[0])
        for link in blue_links:
            if link.pin in exchanges.keys():
                exchanges[link.pin]['blue'].append(link.display)
            else:
                exchanges[link.pin] = dict(red=[], blue=[link.display])
        return list(exchanges.items())

    def _set_pins(self, blue_op):
        for lnk in blue_op.chain:
            fact = next((f for f in lnk.used), None)
            if fact:
                if fact.trait == 'host.process.id':
                    lnk.pin = int(fact.value)
                else:
                    lnk.pin = self._find_original_pid(blue_op.all_relationships(), fact.trait, fact.value)

    def _find_original_pid(self, relationships, trait, value):
        r_source = next((r.source for r in relationships if r.target == (trait, value)), None)
        if r_source:
            if r_source[0] == 'host.process.id':
                return int(r_source[1])
            else:
                return self._find_original_pid(relationships, r_source.trait, r_source.value)
        return 0
