import os
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps

import stripe

from flask import Flask, render_template, url_for, flash, session
from werkzeug.utils import redirect

stripe.api_key = os.environ.get("STRIPE_API_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# Define the life of the session object to timeout after 60 minutes
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)

# Simulate database
store_df = pd.read_csv("store.csv")
store_data = store_df.to_dict('records')


def manage_session(func):
    """Manage user session by creating a new user cart if it does not exists or session timed out"""

    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session:
            # Setting session cart
            session['user_cart'] = {}
            session['items_in_cart'] = 0
            session.modified = True
        return func(*args, **kwargs)

    return wrapper


# Inject new values into the template context
@app.context_processor
def inject_year():
    return {'year': datetime.now().year}


@app.route("/")
@manage_session
def home():
    return render_template("index.html", store_data=store_data)


@app.route("/add/<item_id>")
@manage_session
def add_to_cart(item_id):
    # Reading and updating session cart
    # Initialize item count value to 1 if not in cart already
    if item_id not in session['user_cart']:
        session['user_cart'][item_id] = 1
    # Increment item count if already in cart
    else:
        session['user_cart'][item_id] += 1

    session['items_in_cart'] += 1
    session.modified = True

    flash("The item was added to your shopping cart.")

    return redirect(url_for("home"))


@app.route("/remove/<item_id>")
@manage_session
def remove_from_cart(item_id):
    # If item in user cart remove it
    if item_id in session['user_cart']:
        session['items_in_cart'] -= session['user_cart'].get(item_id)
        del session['user_cart'][item_id]

        session.modified = True
        flash("The selected item has been removed.")
        return redirect(url_for("cart"))
    # Redirect if url called manually
    return redirect(url_for("home"))


@app.route("/clear")
@manage_session
def clear_cart():
    # If user cart has items clear it
    if session['user_cart']:
        session['user_cart'].clear()
        session['items_in_cart'] = 0
        session.modified = True
        flash("All items have been removed.")
    else:
        flash("Your cart is already empty.")
    return redirect(url_for("cart"))


@app.route("/cart")
@manage_session
def cart():
    # Initialize a list and an integer do display cart data and total price in HTML
    final_cart = []
    checkout = []
    total = 0

    # Loop through all items in user cart
    for _id in session['user_cart']:

        # Loop through all items in "database"
        for item in store_data:

            # If item ids are matching
            if item.get("id") == int(_id):
                # Add a new dict to the final_cart list containing item id, name, price, image and count
                # Increment total cart price by item price multiplied by item count
                final_cart.append({"id": item.get("id"),
                                   "item": item.get("item"),
                                   "price": item.get("price"),
                                   "image": item.get("image"),
                                   "count": session['user_cart'].get(_id)})

                checkout.append({'price': item.get("stripe"), 'quantity': session['user_cart'].get(_id)})

                total += item.get("price") * session['user_cart'].get(_id)

    session["checkout"] = checkout
    session.modified = True

    return render_template("cart.html", final_cart=final_cart, total=total)


@app.route('/checkout')
@manage_session
def create_checkout_session():
    if not session['user_cart']:
        flash("Your cart is empty.")
        return redirect(url_for("cart"))

    try:
        # Create a Stripe Checkout Session
        checkout_session = stripe.checkout.Session.create(

            # Define products to sell from user cart
            line_items=session["checkout"],
            payment_method_types=['card'],
            mode='payment',
            success_url="http://localhost:5000/success",
            cancel_url="http://localhost:5000/cancel",

        )

    except Exception as e:

        return str(e)

    return redirect(checkout_session.url, code=303)


@app.route('/cancel')
def cancel_checkout():
    flash("Forgot to add something to your cart? Shop around then come back to pay!")
    return redirect(url_for("home"))


@app.route('/success')
def checkout_success():
    session['user_cart'].clear()
    session.modified = True

    return render_template("success.html")


if __name__ == "__main__":
    app.run(debug=True)
