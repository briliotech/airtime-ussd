"""QuickTop USSD menu.

Brilio sends the subscriber's whole input history as `text` ("1*2*0712345678").
Each request replays that history through the screens below, so no menu state
has to be stored between requests:

* "0" goes back one screen, "00" returns to the main menu.
* Invalid input keeps the subscriber on the same screen with an error line.

The engine is pure: a screen that needs a side effect (e.g. starting an M-Pesa
payment) returns it as `action`, and the view runs it.
"""

from dataclasses import dataclass, field
from functools import partial
from typing import Callable, Optional

from accounts.phone import display_msisdn, normalize_msisdn

MAX_TEXT_LENGTH = 160
BACK = '0'
HOME = '00'


@dataclass
class Context:
    msisdn: str          # 2547XXXXXXXX
    session_id: str
    min_amount: int
    max_amount: int


@dataclass
class Response:
    text: str
    end: bool = False
    action: Optional[Callable] = None


class Invalid(Exception):
    def __init__(self, message='Invalid choice.'):
        super().__init__(message)
        self.message = message


@dataclass
class Screen:
    render: Callable  # (data, ctx) -> Response
    accept: Optional[Callable] = None  # (value, data, ctx) -> next state; None for final screens


def con(text):
    return Response(text)


def end(text, action=None):
    return Response(text, end=True, action=action)


def choose(value, options):
    try:
        return options[value]
    except KeyError:
        raise Invalid() from None


def numbered(title, items, back=True):
    lines = [title] + [f'{i}. {item}' for i, item in enumerate(items, start=1)]
    if back:
        lines.append('0. Back')
    return '\n'.join(lines)


def pick(value, items):
    """Return the item for a 1-based menu choice."""
    if value.isdigit() and 1 <= int(value) <= len(items):
        return items[int(value) - 1]
    raise Invalid()


def parse_amount(value, minimum, maximum):
    if not value.isdigit():
        raise Invalid('Enter amount in whole shillings.')
    amount = int(value)
    if not minimum <= amount <= maximum:
        raise Invalid(f'Amount must be KES {minimum}-{maximum:,}.')
    return amount


# ---------------------------------------------------------------------------
# Main menu
# ---------------------------------------------------------------------------

def main_render(data, ctx):
    return con(numbered('Welcome to QuickTop', ['Buy Airtime', 'Buy Data', 'Pay Utilities', 'Insurance'], back=False))


def main_accept(value, data, ctx):
    return choose(value, {
        '1': 'airtime_target',
        '2': 'data_network',
        '3': 'utility_biller',
        '4': 'insurance_product',
    })


def cancelled_render(data, ctx):
    return end('Request cancelled. Thank you for using QuickTop.')


def coming_soon_render(data, ctx):
    return end(f"{data['product']} is coming soon on QuickTop. You have not been charged.")


def confirm_accept(next_state):
    def accept(value, data, ctx):
        return choose(value, {'1': next_state, '2': 'cancelled'})
    return accept


# ---------------------------------------------------------------------------
# Buy airtime
# ---------------------------------------------------------------------------

def airtime_target_render(data, ctx):
    return con(numbered('Buy Airtime', ['My number', 'Other number']))


def airtime_target_accept(value, data, ctx):
    if value == '1':
        data['recipient'] = ctx.msisdn
        return 'airtime_amount'
    return choose(value, {'2': 'airtime_recipient'})


def airtime_recipient_render(data, ctx):
    return con('Enter phone number to top up\n0. Back')


def airtime_recipient_accept(value, data, ctx):
    recipient = normalize_msisdn(value)
    if recipient is None:
        raise Invalid('Invalid phone number.')
    data['recipient'] = recipient
    return 'airtime_amount'


def airtime_amount_render(data, ctx):
    return con(f'Enter amount (KES {ctx.min_amount}-{ctx.max_amount:,})\n0. Back')


def airtime_amount_accept(value, data, ctx):
    data['amount'] = parse_amount(value, ctx.min_amount, ctx.max_amount)
    return 'airtime_confirm'


def airtime_confirm_render(data, ctx):
    return con(
        f"Buy KES {data['amount']:,} airtime for {display_msisdn(data['recipient'])}\n"
        f'Pay via M-Pesa {display_msisdn(ctx.msisdn)}\n'
        '1. Confirm\n2. Cancel'
    )


def airtime_done_render(data, ctx):
    from airtime.services import start_airtime_purchase

    action = partial(start_airtime_purchase, ctx.session_id, ctx.msisdn, data['recipient'], data['amount'])
    return end(
        f"Enter your M-Pesa PIN when prompted to pay KES {data['amount']:,}. "
        'Airtime will be sent once payment is received.',
        action=action,
    )


# ---------------------------------------------------------------------------
# Buy data (placeholder bundles, purchase not live yet)
# ---------------------------------------------------------------------------

DATA_BUNDLES = {
    'Safaricom': [('1GB 1 hour', 19), ('1.5GB 3 hours', 50), ('2GB 24 hours', 100), ('6GB 7 days', 700)],
    'Airtel': [('1GB 1 hour', 20), ('2GB 24 hours', 99), ('5GB 7 days', 500), ('15GB 30 days', 1000)],
    'MTN': [('1GB 24 hours', 50), ('3GB 7 days', 250), ('10GB 30 days', 1000), ('25GB 30 days', 2000)],
}
NETWORKS = list(DATA_BUNDLES)


def data_network_render(data, ctx):
    return con(numbered('Buy Data - choose network', NETWORKS))


def data_network_accept(value, data, ctx):
    data['network'] = pick(value, NETWORKS)
    return 'data_bundle'


def data_bundle_render(data, ctx):
    bundles = DATA_BUNDLES[data['network']]
    return con(numbered(f"{data['network']} bundles", [f'{name} @ KES {price}' for name, price in bundles]))


def data_bundle_accept(value, data, ctx):
    name, price = pick(value, DATA_BUNDLES[data['network']])
    data.update(bundle=name, price=price)
    return 'data_confirm'


def data_confirm_render(data, ctx):
    return con(f"Buy {data['network']} {data['bundle']} for KES {data['price']}?\n1. Confirm\n2. Cancel")


def data_confirm_accept(value, data, ctx):
    data['product'] = 'Data bundles'
    return choose(value, {'1': 'coming_soon', '2': 'cancelled'})


# ---------------------------------------------------------------------------
# Pay utilities (placeholder, payment not live yet)
# ---------------------------------------------------------------------------

BILLERS = ['ZUKU', 'KPLC Prepaid Tokens', 'KPLC Postpaid']


def utility_biller_render(data, ctx):
    return con(numbered('Pay Utilities', BILLERS))


def utility_biller_accept(value, data, ctx):
    data['biller'] = pick(value, BILLERS)
    return 'utility_account'


def utility_account_render(data, ctx):
    label = 'meter number' if data['biller'].startswith('KPLC') else 'account number'
    return con(f"Enter {data['biller']} {label}\n0. Back")


def utility_account_accept(value, data, ctx):
    if not value.isalnum() or not 4 <= len(value) <= 20:
        raise Invalid('Invalid account number.')
    data['account'] = value
    return 'utility_amount'


def utility_amount_render(data, ctx):
    return con('Enter amount (KES)\n0. Back')


def utility_amount_accept(value, data, ctx):
    data['amount'] = parse_amount(value, 10, 150000)
    return 'utility_confirm'


def utility_confirm_render(data, ctx):
    return con(
        f"Pay KES {data['amount']:,} to {data['biller']}\nAccount: {data['account']}\n1. Confirm\n2. Cancel"
    )


def utility_confirm_accept(value, data, ctx):
    data['product'] = f"{data['biller']} payment"
    return choose(value, {'1': 'coming_soon', '2': 'cancelled'})


# ---------------------------------------------------------------------------
# Insurance (placeholder)
# ---------------------------------------------------------------------------

INSURANCE_PRODUCTS = ['Motor', 'Health', 'Personal Accident', 'Funeral Cover']


def insurance_product_render(data, ctx):
    return con(numbered('Insurance', INSURANCE_PRODUCTS))


def insurance_product_accept(value, data, ctx):
    data['product'] = f'{pick(value, INSURANCE_PRODUCTS)} insurance'
    return 'coming_soon'


SCREENS = {
    'main': Screen(main_render, main_accept),
    'cancelled': Screen(cancelled_render),
    'coming_soon': Screen(coming_soon_render),

    'airtime_target': Screen(airtime_target_render, airtime_target_accept),
    'airtime_recipient': Screen(airtime_recipient_render, airtime_recipient_accept),
    'airtime_amount': Screen(airtime_amount_render, airtime_amount_accept),
    'airtime_confirm': Screen(airtime_confirm_render, confirm_accept('airtime_done')),
    'airtime_done': Screen(airtime_done_render),

    'data_network': Screen(data_network_render, data_network_accept),
    'data_bundle': Screen(data_bundle_render, data_bundle_accept),
    'data_confirm': Screen(data_confirm_render, data_confirm_accept),

    'utility_biller': Screen(utility_biller_render, utility_biller_accept),
    'utility_account': Screen(utility_account_render, utility_account_accept),
    'utility_amount': Screen(utility_amount_render, utility_amount_accept),
    'utility_confirm': Screen(utility_confirm_render, utility_confirm_accept),

    'insurance_product': Screen(insurance_product_render, insurance_product_accept),
}


def handle(text, ctx):
    """Replay the subscriber's input history and return the screen to show now."""
    inputs = text.split('*') if text else []
    state, data, history, error = 'main', {}, [], None

    for raw in inputs:
        value = raw.strip()
        screen = SCREENS[state]
        if screen.accept is None:
            break
        if value == HOME:
            state, data, history, error = 'main', {}, [], None
            continue
        if value == BACK and history:
            state, data = history.pop()
            error = None
            continue
        new_data = dict(data)
        try:
            next_state = screen.accept(value, new_data, ctx)
        except Invalid as exc:
            error = exc.message
            continue
        history.append((state, data))
        state, data, error = next_state, new_data, None

    response = SCREENS[state].render(data, ctx)
    if error and not response.end:
        response.text = f'{error}\n{response.text}'
    return response
