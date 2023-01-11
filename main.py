from flask import Flask, render_template, redirect, url_for, request, abort
from flask_bootstrap import Bootstrap
import stripe
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, logout_user, LoginManager, login_required
from datetime import datetime
from forms import RegisterForm, LoginForm, DeletionForm, AddForm
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
Bootstrap(app)

# Connect to Database
app.app_context().push()
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cafes7.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

login_manager = LoginManager()
login_manager.init_app(app)

owners = [1]
logged_in = False
current_user_id = 0
stripe.api_key = 'sk_test_wU7nrJCZspk1NPDxiQgAF05q'


# user table configuration
class User(db.Model, UserMixin):
    __tablename__ = "user"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    name = db.Column(db.String(250), nullable=False)
    items = relationship("CartItem", back_populates="buyer")


# Cafe TABLE Configuration
class Cafe(db.Model):
    __tablename__ = "cafe"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=True, nullable=False)
    map_url = db.Column(db.String(500), nullable=False)
    img_url = db.Column(db.String(500), nullable=False)
    location = db.Column(db.String(250), nullable=False)
    seats = db.Column(db.String(250), nullable=False)
    has_toilet = db.Column(db.Boolean, nullable=False)
    has_wifi = db.Column(db.Boolean, nullable=False)
    has_sockets = db.Column(db.Boolean, nullable=False)
    can_take_calls = db.Column(db.Boolean, nullable=False)
    coffee_price = db.Column(db.String(250), nullable=True)
    item_in_cart = relationship("CartItem", back_populates="cafe")

    def to_dictionary(self):
        return {column.name: getattr(self, column.name) for column in self.__table__.columns}


class CartItem(db.Model):
    __tablename__ = "cart_item"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), unique=False, nullable=False)
    coffee_price = db.Column(db.String(250), nullable=True)
    img_url = db.Column(db.String(500), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    buyer = relationship("User", back_populates="items")
    cafe_id = db.Column(db.Integer, db.ForeignKey('cafe.id'))
    cafe = relationship("Cafe", back_populates="item_in_cart")


# db.create_all()

# create Stripe products and prices
items = Cafe.query.all()
stripe_products = {}
stripe_prices = {}
for item in items:
    stripe_products[str(item.id)] = stripe.Product.create(
        # id=item.id,
        name=item.name,
        images=[item.img_url, item.map_url]
    )
    stripe_prices[str(item.id)] = stripe.Price.create(
        currency="cad",
        product=stripe_products[str(item.id)].id,
        unit_amount=int(float(item.coffee_price.replace("£", "")) * 100),
    )


@app.context_processor
def inject_now():
    return {'now': datetime.utcnow()}


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


def admin_only(function):
    @wraps(function)
    def wrapper_function(*args, **kwargs):
        if current_user_id == 1:
            return function(*args, **kwargs)
        else:
            return abort(403, "You are not authorized to view this page, sucker hahaha.")

    return wrapper_function


@app.route("/")
def home():
    all_cafes = Cafe.query.all()
    return render_template("index.html", all_cafes=all_cafes,
                           logged_in=logged_in, current_user_id=current_user_id,
                           owners=owners, type="home")


@app.route('/register', methods=["POST", "GET"])
def register():
    register_form = RegisterForm()
    if register_form.validate_on_submit():
        new_user = User()
        new_user.email = request.form["email"]
        new_user.name = request.form["name"]
        user_in_db = User.query.filter_by(email=new_user.email).first()
        if user_in_db:
            error = "You already have signed up with that email, log in instead."
            login_form = LoginForm()
            return render_template("login.html", form=login_form, error=error)
        new_user.password = generate_password_hash(
            password=request.form["password"],
            method="pbkdf2:sha256",
            salt_length=8
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        global logged_in, current_user_id
        logged_in = True
        current_user_id = new_user.id
        return redirect(url_for("home", logged_in=logged_in))
    return render_template("register.html", form=register_form)


@app.route('/login', methods=["POST", "GET"])
def login():
    login_form = LoginForm()
    error = None
    if login_form.validate_on_submit():
        email_entered = request.form["email"]
        password_entered = request.form["password"]
        user_in_db = User.query.filter_by(email=email_entered).first()
        if user_in_db:
            password_in_db = user_in_db.password
            if check_password_hash(pwhash=password_in_db, password=password_entered):
                login_user(user_in_db)
                global logged_in, current_user_id
                logged_in = True
                current_user_id = user_in_db.id
                return redirect(url_for("home"))
            else:
                error = "Invalid Password"
        else:
            error = "No user with that email exists."
    return render_template("login.html", form=login_form, error=error)


@app.route('/logout')
@login_required
def logout():
    logout_user()
    global logged_in, current_user_id
    logged_in = False
    current_user_id = 0
    return redirect(url_for('home'))


@app.route('/add_cafe', methods=["GET", "POST"])
@login_required
def add_cafe():
    add_form = AddForm()
    if add_form.validate_on_submit():
        new_cafe = Cafe(
            name=add_form.name.data,
            location=add_form.location.data,
            map_url=add_form.map_url.data,
            img_url=add_form.img_url.data,
            seats=add_form.seats.data,
            coffee_price=add_form.coffee_price.data,
            has_toilet=True if add_form.has_toilet.data.lower() == "yes" else False,
            has_wifi=True if add_form.has_wifi.data.lower() == "yes" else False,
            has_sockets=True if add_form.has_sockets.data.lower() == "yes" else False,
            can_take_calls=True if add_form.can_take_calls.data.lower() == "yes" else False
        )
        db.session.add(new_cafe)
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("add_cafe.html", form=add_form, logged_in=logged_in)


@app.route("/delete/<int:post_id>", methods=["POST", "GET"])
@admin_only
def delete_post(post_id):
    post_to_delete = Cafe.query.get(post_id)
    form = DeletionForm()
    if form.validate_on_submit():
        if form.cancel.data:
            return redirect(url_for("home"))
        elif form.delete.data:
            db.session.delete(post_to_delete)
            db.session.commit()
            return redirect(url_for('home'))
    return render_template("deletion_confirmation.html", form=form, post_to_delete=post_to_delete)


@app.route("/edit-post/<int:post_id>", methods=["POST", "GET"])
@admin_only
def edit_post(post_id):
    cafe = Cafe.query.get(post_id)
    edit_form = AddForm(
        name=cafe.name,
        location=cafe.location,
        img_url=cafe.img_url,
        map_url=cafe.map_url,
        seats=cafe.seats,
        coffee_price=cafe.coffee_price,
        has_toilet="Yes" if cafe.has_toilet else "No",
        has_wifi="Yes" if cafe.has_wifi else "No",
        has_sockets="Yes" if cafe.has_sockets else "No",
        can_take_calls="Yes" if cafe.can_take_calls else "No"
    )
    if edit_form.validate_on_submit():
        cafe.name = edit_form.name.data
        cafe.location = edit_form.location.data
        cafe.map_url = edit_form.map_url.data
        cafe.img_url = edit_form.img_url.data
        cafe.seats = edit_form.seats.data
        cafe.coffee_price = "£" + edit_form.coffee_price.data
        cafe.has_toilet = True if edit_form.has_toilet.data.lower() == "yes" else False
        cafe.has_wifi = True if edit_form.has_wifi.data.lower() == "yes" else False
        cafe.has_sockets = True if edit_form.has_sockets.data.lower() == "yes" else False
        cafe.can_take_calls = True if edit_form.can_take_calls.data.lower() == "yes" else False
        db.session.commit()
        return redirect(url_for("home"))
    return render_template("add_cafe.html", form=edit_form, logged_in=logged_in)


@app.route('/cart', methods=["POST", "GET"])
def cart():
    current_user = User.query.get(current_user_id)
    items_in_cart = current_user.items
    if request.method == "POST":
        item_id = request.form["cart-button"]
        item_to_add = Cafe.query.get(item_id)
        item_in_cart = CartItem.query.filter_by(name=item_to_add.name, buyer_id=current_user_id).first()
        if item_in_cart:
            print(item_in_cart.quantity)
            item_in_cart.quantity += 1
            db.session.commit()
        else:
            new_item = CartItem(
                name=item_to_add.name,
                coffee_price=item_to_add.coffee_price,
                buyer_id=current_user_id,
                cafe_id=item_to_add.id,
                img_url=item_to_add.img_url,
                quantity=1,
            )
            db.session.add(new_item)
            db.session.commit()
        return redirect(url_for("cart"))
    return render_template("index.html", logged_in=logged_in, current_user_id=current_user_id,
                           owners=owners, type="cart", all_cafes=items_in_cart)


@app.route("/add-one", methods={"POST"})
def add_one():
    item_id = request.form["add-button"]
    current_item = CartItem.query.get(item_id)
    current_item.quantity += 1
    db.session.commit()
    return redirect(url_for("cart"))


@app.route("/minus-one", methods={"POST"})
def minus_one():
    item_id = request.form["minus-button"]
    current_item = CartItem.query.get(item_id)
    if current_item.quantity > 1:
        current_item.quantity -= 1
        db.session.commit()
    elif current_item.quantity == 1:
        db.session.delete(current_item)
        db.session.commit()
    return redirect(url_for("cart"))


@app.route("/delete-from-cart", methods={"POST"})
def delete_from_cart():
    item_id = request.form["cart-delete"]
    item_to_delete = CartItem.query.get(item_id)
    db.session.delete(item_to_delete)
    db.session.commit()
    return redirect(url_for("cart"))


@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    cart_cafe_id = request.form["checkout-button"]
    print(cart_cafe_id)
    cafe_to_checkout = CartItem.query.get(cart_cafe_id)
    inventory_cafe_id = Cafe.query.filter_by(name=cafe_to_checkout.name).first().id
    product_id = stripe_products[str(inventory_cafe_id)].id
    price_id = stripe_prices[str(inventory_cafe_id)].id
    try:
        checkout_session = stripe.checkout.Session.create(
            line_items=[
                {
                    # Provide the exact Price ID (for example, pr_1234) of the product you want to sell
                    'price': price_id,
                    'quantity': cafe_to_checkout.quantity,
                },
            ],
            mode='payment',
            success_url='http://127.0.0.1:5000/success.html',
            cancel_url='http://127.0.0.1:5000/cancel.html',
        )
    except Exception as e:
        return str(e)

    return redirect(checkout_session.url, code=303)


if __name__ == "__main__":
    app.run(debug=True)
