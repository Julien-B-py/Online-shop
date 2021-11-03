import json
import os
import pandas as pd
from datetime import datetime, timedelta
from functools import wraps

import stripe

from flask import Flask, render_template, url_for, flash, session
from flask_login import login_user, current_user, UserMixin, LoginManager, logout_user
from flask_sqlalchemy import SQLAlchemy
from werkzeug.utils import redirect

from forms import RegisterForm, LoginForm

stripe.api_key = os.environ.get("STRIPE_API_KEY")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

# Define the life of the session object to timeout after 60 minutes
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(minutes=60)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100), unique=True)
    password = db.Column(db.String(100))
    cart = db.Column(db.String())


db.create_all()

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
            session['items_in_cart'] = sum(session['user_cart'].values())
            session.modified = True
        return func(*args, **kwargs)

    return wrapper


# Inject new values into the template context
@app.context_processor
def inject_year():
    return {'year': datetime.now().year,
            'current_user': current_user, }


@app.route("/")
@manage_session
def home():
    session['items_in_cart'] = sum(session['user_cart'].values())
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

    user = current_user
    user.cart = json.dumps(session['user_cart'])
    db.session.commit()

    session['items_in_cart'] = sum(session['user_cart'].values())
    session.modified = True

    flash("The item was added to your shopping cart.")

    return redirect(url_for("home"))


@app.route("/remove/<item_id>")
@manage_session
def remove_from_cart(item_id):
    # If item in user cart remove it
    if item_id in session['user_cart']:
        del session['user_cart'][item_id]
        session['items_in_cart'] = sum(session['user_cart'].values())
        user = current_user
        user.cart = json.dumps(session['user_cart'])
        db.session.commit()

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
        session['items_in_cart'] = sum(session['user_cart'].values())
        user = current_user
        user.cart = json.dumps(session['user_cart'])
        db.session.commit()

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


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        user = User(
            name=form.name.data,
            email=form.email.data,
            password=form.password.data,
            cart=json.dumps(session['user_cart']),
        )

        db.session.add(user)
        db.session.commit()
        login_user(user)

        flash("Account successfully created!")

        return redirect(url_for("home"))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()

    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data

        user = User.query.filter_by(email=email).first()

        if not user:
            flash('Incorrect email')
            return redirect(url_for("login"))

        if password != user.password:
            flash('Incorrect password')
            return render_template("login.html", form=form)

        login_user(user)

        session['user_cart'] = json.loads(user.cart)

        return redirect(url_for("home"))

    return render_template("login.html", form=form)


@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for("home"))


if __name__ == "__main__":
    app.run(debug=True)
