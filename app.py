import os

from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from tempfile import mkdtemp
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, lookup, usd

# Configure application
app = Flask(__name__)

# Ensure templates are auto-reloaded
app.config["TEMPLATES_AUTO_RELOAD"] = True

# Custom filter
app.jinja_env.filters["usd"] = usd

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///finance.db")

# Make sure API key is set
if not os.environ.get("API_KEY"):
    raise RuntimeError("API_KEY not set")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show portfolio of stocks"""
    rows= db.execute("SELECT stocksymbol, company, SUM(shares) as shares, AVG(share_price) as price, SUM(shares*share_price) as total\
                    FROM stocks WHERE userid=?\
                    GROUP BY stocksymbol, company", session["user_id"])


    # finding how much money user has
    cash_left= db.execute("SELECT cash FROM users WHERE id=?", session["user_id"])[0]
    cash_left= cash_left['cash']

    # finding how much is the bought stocks worth
    total_stocks_prices= db.execute("SELECT SUM(share_price*shares) AS stocks_price FROM stocks\
                                     WHERE userid=?", session["user_id"])[0]
    total_stocks_prices= total_stocks_prices["stocks_price"]

    if total_stocks_prices== None or total_stocks_prices=="":
        total_stocks_prices=0

    return render_template('index.html', rows=rows, cash=usd(cash_left), total= usd(total_stocks_prices+cash_left))


@app.route("/buy", methods=["GET", "POST"])
@login_required
def buy():
    """Buy shares of stock"""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        num_shares = request.form.get('shares')
        if symbol == "":
            return apology("Enter a stock symbol")
        if num_shares == "":
            return apology("Enter the number of stocks you would like to buy")
        try:
            num_shares=int(num_shares)
        except ValueError:
            return apology("Number of stocks must be a positive integer")
        if int(num_shares)<0:
            return apology("Number of stocks must be a positive integer")

        result = lookup(symbol)
        if result is None:
            return apology("Invalid stock symbol")
        else:
            stock_price = result['price']
            symbol= result['symbol']
            company= result["name"]

            rows= db.execute("SELECT cash FROM users WHERE id= ?", session["user_id"])


            if stock_price*num_shares > rows[0]['cash']:
                return apology("Insufficient Funds")
            else:
                cost= stock_price*num_shares
                db.execute("UPDATE users SET cash= ? WHERE id=?", rows[0]['cash']-cost, session["user_id"])
                db.execute("INSERT INTO stocks (userid, stocksymbol, shares, share_price, status, company) VALUES (?, ?, ?, ?, 'buying', ?)",
                session["user_id"], symbol, num_shares, stock_price, company)

                # Redirect user to home page
                return redirect("/")
    else:
        return render_template("buy.html")


@app.route("/history")
@login_required
def history():
    """Show history of transactions"""
    rows= db.execute("SELECT stocksymbol, shares, share_price, Timestamp FROM stocks WHERE userid=?", session['user_id'])
    print("ROWSSSSSSSSS", rows)
    return render_template("history.html", rows=rows)


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""

    # Forget any user_id
    session.clear()

    # User reached route via POST (as by submitting a form via POST)
    if request.method == "POST":

        # Ensure username was submitted
        if not request.form.get("username"):
            return apology("must provide username", 403)

        # Ensure password was submitted
        elif not request.form.get("password"):
            return apology("must provide password", 403)

        # Query database for username
        rows = db.execute("SELECT * FROM users WHERE username = ?",
                          request.form.get("username"))

        # Ensure username exists and password is correct
        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], request.form.get("password")):
            return apology("invalid username and/or password", 403)

        # Remember which user has logged in
        session["user_id"] = rows[0]["id"]

        # Redirect user to home page
        return redirect("/")

    # User reached route via GET (as by clicking a link or via redirect)
    else:
        return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""

    # Forget any user_id
    session.clear()

    # Redirect user to login form
    return redirect("/")


@app.route("/quote", methods=["GET", "POST"])
@login_required
def quote():
    """Get stock quote."""
    if request.method == "POST":
        symbol = request.form.get("symbol")
        # print("symbol: ",symbol)
        result = lookup(symbol)
        if result is None:
            # print(result)
            return apology("No stock found with the entered symbol")
        else:
            return render_template("quoted.html", stock_company=result["name"], stock_symbol=result["symbol"],
                                   stock_price=usd(result["price"]))

    else:
        return render_template("quote.html")


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    session.clear()
    # a user is trying to register for the webiste (post request)
    if request.method == "POST":
        username = request.form.get("username")
        password = request.form.get("password")
        password_confirmation = request.form.get("confirmation")
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        if not username:
            return apology("must provide username")
        elif len(rows) > 0:
            return apology("username already taken, provide another one")
        elif (not password) or (not password_confirmation):
            return apology("must provide a password and a password confirmation")
        elif password != password_confirmation:
            return apology("password and its confirmation does not match please re-enter them")

        pw_hash = generate_password_hash(password)
        db.execute("INSERT INTO users (username, hash) VALUES( ?, ?)",
                   username, pw_hash)


        # tracking which users has signed in
        rows = db.execute("SELECT * FROM users WHERE username = ?", username)
        # print(rows[0]['id'])
        session["user_id"] = rows[0]["id"]

        # returning the user to the home page
        return redirect("/")

    else:  # user is going to the registration page (get request)
        return render_template("register.html")


@app.route("/sell", methods=["GET", "POST"])
@login_required
def sell():
    """Sell shares of stock"""
    stock_symbols= db.execute("SELECT DISTINCT(stocksymbol) FROM stocks WHERE userid=? AND status='buying'", session["user_id"])
    # shares_owned_stock=

    if request.method== "POST":
        input_symbol= request.form.get("symbol")
        input_shares= request.form.get("shares")
        try:
            input_shares= int(input_shares)
        except ValueError:
            return apologu("Number of shares should be a positvie integer")
        # checking the db to get how many shares the user own of input stock
        bougt_shares= db.execute("SELECT SUM(shares) AS shares FROM stocks WHERE stocksymbol=? AND userid=? AND status= 'buying'",\
                    input_symbol, session["user_id"])[0]['shares']
        sold_shares= db.execute("SELECT SUM(shares) AS shares FROM stocks WHERE stocksymbol=? AND userid=? AND status= 'selling'",\
                    input_symbol, session["user_id"])[0]['shares']
        if bougt_shares== None:
            bougt_shares=0
        if sold_shares== None:
            sold_shares=0

        owned_shares= bougt_shares-sold_shares

        if input_shares<=0:
            return apology("Shares must be positive integer")
        if input_shares> owned_shares:
            return apology(f"You only own {owned_shares} of {input_symbol}")
        else:
            result = lookup(input_symbol)
            stock_price = result['price']
            symbol= result['symbol']
            company= result["name"]

            db.execute("INSERT INTO stocks (userid, stocksymbol, shares, share_price, company, status)\
                        VALUES (?, ?, ?, ?, ?, 'selling')", session['user_id'], input_symbol, -1*input_shares, stock_price, company)

            cash_to_add_to_user_account= stock_price*input_shares
            cash= db.execute("SELECT cash from users WHERE id=?", session["user_id"])[0]['cash'] #amount of case already in user account

            print("HERE: ", cash, cash_to_add_to_user_account)
            updated_cash= cash_to_add_to_user_account+cash
            db.execute("UPDATE users SET cash=? WHERE id=?", updated_cash, session['user_id'])

            return redirect('/')
    else:
        return render_template("sell.html", stocks= stock_symbols)
    # return apology("TODO")
