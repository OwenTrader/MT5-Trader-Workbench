import json
import urllib.error
import urllib.request

from python_service.app.models.order_sync import TopStepAccountCredential


API_BASE_URL = 'https://api.topstepx.com'


class TopStepApiError(Exception):
    pass


class TopStepClient:
    def __init__(self, credential: TopStepAccountCredential):
        self.credential = credential
        self.token: str | None = None

    def _request(self, path: str, payload: dict | None = None, authenticated: bool = True) -> dict:
        body = json.dumps(payload or {}).encode('utf-8')
        headers = {
            'accept': 'text/plain',
            'Content-Type': 'application/json',
        }
        if authenticated:
            token = self.get_token()
            headers['Authorization'] = f'Bearer {token}'

        request = urllib.request.Request(
            f'{API_BASE_URL}{path}',
            data=body,
            headers=headers,
            method='POST',
        )

        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                response_body = response.read().decode('utf-8')
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode('utf-8', errors='replace')
            raise TopStepApiError(f'TopStep HTTP {exc.code}: {detail}') from exc
        except urllib.error.URLError as exc:
            raise TopStepApiError(f'TopStep request failed: {exc.reason}') from exc

        data = json.loads(response_body) if response_body else {}
        if data.get('success') is False:
            raise TopStepApiError(data.get('errorMessage') or f'TopStep error {data.get("errorCode")}')
        return data

    def get_token(self) -> str:
        if self.token:
            return self.token

        data = self._request(
            '/api/Auth/loginKey',
            {
                'userName': self.credential.user_name,
                'apiKey': self.credential.api_key,
            },
            authenticated=False,
        )
        token = data.get('token')
        if not token:
            raise TopStepApiError('TopStep login did not return a token')
        self.token = token
        return token

    def place_market_order(self, contract_id: str, side: str, size: int, custom_tag: str | None = None) -> int | None:
        data = self._request('/api/Order/place', {
            'accountId': self.credential.account_id,
            'contractId': contract_id,
            'type': 2,
            'side': 0 if side == 'buy' else 1,
            'size': size,
            'limitPrice': None,
            'stopPrice': None,
            'trailPrice': None,
            'customTag': custom_tag,
            'stopLossBracket': None,
            'takeProfitBracket': None,
        })
        return data.get('orderId')

    def close_contract_position(self, contract_id: str) -> None:
        self._request('/api/Position/closeContract', {
            'accountId': self.credential.account_id,
            'contractId': contract_id,
        })
