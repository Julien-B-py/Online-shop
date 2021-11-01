import os

import pandas as pd

from flask import Flask, render_template, url_for, flash
from werkzeug.utils import redirect

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY")

store_df = pd.read_csv("store.csv")
store_data = store_df.to_dict('records')

user_cart = {}


@app.route("/")
def home():
    return render_template("index.html", store_data=store_data)


@app.route("/add/<item_id>")
def add_to_cart(item_id):
    if item_id not in user_cart:
        user_cart[item_id] = 1
    else:
        user_cart[item_id] += 1

    flash("The item was added to your shopping cart.")

    return redirect(url_for("home"))


@app.route("/remove/<item_id>")
def remove_from_cart(item_id):
    del user_cart[item_id]
    flash("The selected item has been removed.")
    return redirect(url_for("cart"))


@app.route("/clear")
def clear_cart():
    if user_cart:
        user_cart.clear()
        flash("All items have been removed.")
    else:
        flash("Your cart is already empty.")
    return redirect(url_for("cart"))


@app.route("/cart")
def cart():
    final_cart = []
    total = 0

    for item in store_data:
        for _id in user_cart:
            if item.get("id") == int(_id):
                final_cart.append({"id": item.get("id"),
                                   "item": item.get("item"),
                                   "price": item.get("price"),
                                   "image": item.get("image"),
                                   "count": user_cart.get(_id)})

                total += item.get("price") * user_cart.get(_id)

    return render_template("cart.html", final_cart=final_cart, total=total)


@app.route("/checkout")
def checkout():
    return "Checkout"


if __name__ == "__main__":
    app.run(debug=True)
