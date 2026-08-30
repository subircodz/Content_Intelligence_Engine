"""
Second OOP / exception-handling practical.

Focus:
- custom exception hierarchy
- exception translation
- exception propagation
- try / except / else / finally
- application-layer vs provider-layer responsibility
- class attribute vs instance attribute

Submitted implementation preserved as practiced.
"""

import time


class PaymentError(Exception):
    pass


class GatewayDeclinedError(PaymentError):
    pass


class PaymentProvider:
    provider_balance = 0

    def charge(self, amount):
        """Charge and update provider balance."""
        if amount < 0:
            raise ValueError("Charge amount cannot be less than zero")
        try:
            print("Processing...")
            time.sleep(5)
            self.provider_balance += amount
            return amount
        except ConnectionError as e:
            raise PaymentError(
                "Could not process payment. Connection Error"
            ) from e
        except TimeoutError as e:
            raise PaymentError(
                "Could not process payment. Connection Timed Out"
            ) from e
        except GatewayDeclinedError:
            raise


def process_payment(amount):
    """Process amount and return transaction amount."""
    txn = PaymentProvider()
    if amount < 0:
        raise ValueError("Amount cannot be less than 0")
    try:
        txn_amount = txn.charge(amount)
    except GatewayDeclinedError:
        print("Error: Payment Gateway Decline")
    except PaymentError as e:
        print(e)
    except Exception as e:
        print(e)
    else:
        print(f"Thank you for Rs. {txn_amount} transaction")
    finally:
        print("Connection pipeline cleaned")


process_payment(500)


"""
Observation:

I could have taken process_payment inside the class. But then again thought,
process payment is application layer, charge is underlying layer.

Later refinement:
GatewayDeclinedError currently has no raise condition in this implementation,
so its handlers are not exercised yet. A later practical can introduce a
simulated gateway-decline condition without introducing a Bank parent class.
"""
