from os import abort

from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
import urllib
from flask_migrate import Migrate
import joblib
import pandas as pd
from datetime import datetime


encoded_password = urllib.parse.quote("Bree@2002!")
app = Flask(__name__)
app.config['SECRET_KEY'  ] = 'super_secret_key'  # Change this to a strong secret key in production
app.config['SQLALCHEMY_DATABASE_URI'] = f'postgresql://postgres:{encoded_password}@localhost:5432/userProfile'
db = SQLAlchemy(app, session_options={"expire_on_commit": False})
migrate = Migrate(app, db)

class Users(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)
    gender = db.Column(db.String(10), nullable=False)


class PredictionHistory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    prediction_type = db.Column(db.String(50), nullable=False)
    likelihood = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)


@app.route('/')
def home():
    if 'user_id' in session:
        # If logged in, redirect to the prediction page
        return redirect(url_for('prediction'))
        # If not logged in via session, check if the user is remembered via cookie
    elif 'user_id' in request.cookies:
        user_id = request.cookies.get('user_id')
        # Validate user_id (optional depending on your application)
        user = Users.query.filter_by(id=user_id).first()
        if user:
            # If user is valid, log them in using session and redirect to the prediction page
            session['user_id'] = user.id
            session['username'] = user.username
            return redirect(url_for('prediction'))
        else:
            # If user_id in cookie is invalid or expired, render the login page
            return render_template('login.html')
        # If neither session nor cookie is present, render the landing page
    else:
        return render_template('index.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        username = request.form['username']
        password = request.form['password']
        dob = request.form['dob']
        gender = request.form['gender']





        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        # Create a new user instance
        new_user = Users(email=email, username=username, password=hashed_password,
                          date_of_birth=dob, gender=gender)

        db.session.add(new_user)
        db.session.commit()

        # Print a confirmation message
        print("User registered successfully!")

        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        remember_me = request.form.get('remember_me')  # Check if 'Remember me' checkbox is checked

        user = Users.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):
            flash('Login successful!', 'success')
            print("User ID:", user.id)  # Add this line for debugging
            session['user_id'] = user.id
            session['username'] = user.username

            # If 'Remember me' checkbox is checked, set a long-lived cookie
            if remember_me:
                resp = make_response(redirect(url_for('prediction')))
                resp.set_cookie('user_id', str(user.id), max_age=3 * 60 * 60)  # expiresd: 3 hours
                return resp

            return redirect(url_for('prediction'))
        else:
            flash('Login failed. Please check your email and password.', 'danger')

    return render_template('login.html')




dia_path='/home/jeptoo/ext/Python/project1/rc.joblib'
rc=joblib.load(dia_path)
model_path='/home/jeptoo/ext/Python/project1/rfc.joblib'
rfc = joblib.load(model_path)


@app.route('/hypertension', methods=['POST', 'GET'])
def hypertension():
    if request.method == 'POST':
        # Get user inputs from the HTML form

        high_chol = float(request.form['high_chol'])
        smoker = float(request.form['smoker'])
        phys_activity = float(request.form['phys_activity'])
        hvy_alcohol = float(request.form['hvy_alcohol'])
        phys_hlth = float(request.form['phys_hlth'])
        height = float(request.form['height'])
        weight = float(request.form['weight'])
        # Retrieve user details from the database
        user = Users.query.filter_by(username=session.get('username')).first()

        # Calculate age
        date_of_birth = user.date_of_birth
        current_date = datetime.now().date()
        age = current_date.year - date_of_birth.year - (
                    (current_date.month, current_date.day) < (date_of_birth.month, date_of_birth.day))
        sex=user.gender

        # Calculate BMI

        bmi = weight / (height ** 2)  # height is assumed to be in centimeters

        # Print out the values for debugging
        print(f"Height: {height}")
        print(f"Weight: {weight}")
        print(f"BMI: {bmi}")

        # Create a DataFrame from user inputs
        user_data = pd.DataFrame([[age, sex, high_chol, bmi, smoker, phys_activity, hvy_alcohol, phys_hlth]],
                                 columns=['Age', 'Sex', 'HighChol', 'BMI', 'Smoker', 'PhysActivity',
                                          'HvyAlcoholConsump', 'PhysHlth'])

        # Use the pre-trained model to make predictions
        likelihood = rfc.predict_proba(user_data)[:, 1].item() * 100

        # Save prediction history to the database
        user_id = session.get('user_id')
        new_prediction = PredictionHistory(user_id=user_id, prediction_type='Hypertension', likelihood=likelihood)
        db.session.add(new_prediction)
        db.session.commit()

        # Return the likelihood to the user
        username = session.get('username')
        success = True
        message = f'Hello {username}, your likelihood to hypertension is: {likelihood:.2f}%.'

        diet_recommendation,need_diet_help = recommend_diets(bmi, hvy_alcohol)
        exercise_recommendation, need_exercise_help = recommend_exercise(phys_activity)
        lifestyle_recommendation, need_lifestyle_help = recommend_lifestyle_changes(hvy_alcohol, smoker)

        # Filter out irrelevant recommendations based on user habits
        recommendations = []
        if hvy_alcohol in [0, 1]:
            recommendations.append(diet_recommendation)
        if phys_activity in [1, 0]:
            recommendations.append(exercise_recommendation)
        if hvy_alcohol in [0, 1] or smoker in [1, 0]:
            recommendations.append(lifestyle_recommendation)

        print(f"REC: {diet_recommendation}")
        print(f"RECr: {exercise_recommendation}")
        # Render the template with the prediction data and other variables
        if likelihood > 50:
            health_alert = "Your risk level is too high. Please visit the hospital for further evaluation."
        else:
            health_alert = None

        print(f"RECrr: {health_alert}")

        return render_template('recohbp.html', prediction=True, likelihood=likelihood, username=username,
                               success=success, message=message, diet_recommendation=diet_recommendation,
                               exercise_recommendation=exercise_recommendation,
                               lifestyle_recommendation=lifestyle_recommendation,need_diet_help=need_diet_help,
                               need_exercise_help=need_exercise_help,
                               need_lifestyle_help=need_lifestyle_help,health_alert=health_alert)

    # If it's a GET request, render the form
    return render_template('hypertension.html', prediction=None)


@app.route('/diabetes', methods=['POST', 'GET'])
def diabetes():
    if request.method == 'POST':
        # Get user inputs from the HTML form

        high_chol = float(request.form['high_chol'])
        height = float(request.form['height'])
        weight =float( request.form['weight'])
        smoker = float(request.form['smoker'])
        phys_activity = float(request.form['phys_activity'])
        phys_hlth = float(request.form['phys_hlth'])
        fruits = float(request.form['fruits'])
        veggies = float(request.form['veggies'])
        hvy_alcohol = float(request.form['hvy_alcohol'])
        high_bp = float(request.form['high_bp'])

        user = Users.query.filter_by(username=session.get('username')).first()

        # Calculate age
        date_of_birth = user.date_of_birth
        current_date = datetime.now().date()
        age = current_date.year - date_of_birth.year - (
                (current_date.month, current_date.day) < (date_of_birth.month, date_of_birth.day))
        sex = user.gender

        # Calculate BMI

        bmi = weight / (height ** 2)  # height is assumed to be in centimeters

        # Print out the values for debugging
        print(f"Height: {height}")
        print(f"Weight: {weight}")
        print(f"BMI: {bmi}")

        # Create a DataFrame from user inputs
        user_data = pd.DataFrame(
            [[age, sex, high_chol, bmi, smoker, phys_activity, phys_hlth, fruits, veggies, hvy_alcohol, high_bp]],
            columns=['Age', 'Sex', 'HighChol', 'BMI', 'Smoker', 'PhysActivity', 'PhysHlth', 'Fruits', 'Veggies',
                     'HvyAlcoholConsump', 'HighBP'])
        # Use the pre-trained model to make predictions
        likelihood = rc.predict_proba(user_data)[:, 1].item() * 100

        # Get user ID from the session
        user_id = session.get('user_id')

        # Save prediction history to the database
        new_prediction = PredictionHistory(user_id=user_id, prediction_type='Diabetes', likelihood=likelihood)
        db.session.add(new_prediction)
        db.session.commit()

        username = session.get('username')
        # Return the likelihood to the user
        success = True
        message = f'Hello {username}, your likelihood to diabetes is: {likelihood:.2f}%. '

        diet_recommendation, need_diet_help = recommend_diet(bmi, hvy_alcohol, veggies, fruits)
        exercise_recommendation, need_exercise_help = recommend_exercise(phys_activity)
        lifestyle_recommendation, need_lifestyle_help = recommend_lifestyle_changes(hvy_alcohol, smoker)

        # Filter out irrelevant recommendations based on user habits
        recommendations = []
        if hvy_alcohol in [0, 1]:
            recommendations.append(diet_recommendation)
        if phys_activity in [1, 0]:
            recommendations.append(exercise_recommendation)
        if hvy_alcohol in [0, 1] or smoker in [1, 0]:
            recommendations.append(lifestyle_recommendation)

        print(f"REC: {diet_recommendation}")
        print(f"RECr: {exercise_recommendation}")

        if likelihood > 50:
            health_alert = "Your risk level is too high. Please visit the hospital for further evaluation."
        else:
            health_alert = None

        print(f"RECrr: {health_alert}")
        # Render the template with the prediction data and other variables
        return render_template('recohbp.html', prediction=True, likelihood=likelihood, username=username,
                               success=success, message=message, diet_recommendation=diet_recommendation,
                               exercise_recommendation=exercise_recommendation,
                               lifestyle_recommendation=lifestyle_recommendation,
                               need_diet_help=need_diet_help,
                               need_exercise_help=need_exercise_help,
                               need_lifestyle_help=need_lifestyle_help,health_alert=health_alert)
    # If it's a GET request, render the form
    return render_template('diabetes.html', prediction=None)

def recommend_diet(bmi, hvy_alcohol, veggies, fruits):
    if hvy_alcohol == 0 and veggies == 1 and fruits == 1 and bmi < 30:
        recommendation = "Your dietary habits seem to be in good shape. Continue to maintain a balanced diet with emphasis on whole grains, fruits, and vegetables. Ensure you're consuming a variety of nutrient-rich foods for optimal health."
        need_help = False
    else:
        recommendation = "Consider making improvements to your diet by reducing alcohol consumption, increasing vegetable and fruit intake, and focusing on healthier food choices."
        need_help = True

    return recommendation, need_help

def recommend_exercise(phys_activity):
    if phys_activity == 1:
        recommendation = "Congratulations on your commitment to regular physical activity! Keep up the good work by maintaining your current exercise regimen. Remember to include a mix of aerobic and strength training exercises for overall fitness."
        need_help = False
    else:
        recommendation = "Regular physical activity is essential for maintaining good health. Aim to increase your activity level gradually until you're meeting recommended guidelines."
        need_help = True

    return recommendation, need_help

def recommend_diets(bmi, hvy_alcohol):
    if hvy_alcohol == 0 and bmi < 30:
        recommendation = "Your dietary habits seem to be in good shape. Continue to maintain a balanced diet with emphasis on whole grains, fruits, and vegetables. Ensure you're consuming a variety of nutrient-rich foods for optimal health."
        need_help = False
    else:
        recommendation = "Consider making improvements to your diet by reducing alcohol consumption, increasing vegetable and fruit intake, and focusing on healthier food choices."
        need_help = True

    return recommendation, need_help

def recommend_lifestyle_changes(hvy_alcohol, smoker):
    if hvy_alcohol == 0 and smoker == 0:
        recommendation = "You're making healthy lifestyle choices by avoiding heavy alcohol consumption and not smoking. Keep it up to reduce your risk of chronic diseases and improve overall well-being."
        need_help = False
    elif hvy_alcohol == 1 or smoker == 1:
        recommendation = "It's important to address high alcohol consumption and smoking habits as they can negatively impact your health. Consider seeking support to reduce alcohol intake and quit smoking for better overall well-being."
        need_help = True
    else:
        recommendation = "Make a conscious effort to adopt healthier lifestyle habits, such as reducing alcohol consumption and avoiding smoking. Small changes can lead to significant improvements in your health over time."
        need_help = True

    return recommendation, need_help


@app.route('/prediction')
def prediction():
    # Retrieve the username from the session
    username = session.get('username', None)

    # Fetch user profiles from the database
    users = Users.query.all()

    # Render the prediction.html template and pass the username and user profiles
    return render_template('pred.html', username=username, users=users)

@app.route('/results_history')
def results_history():
    # Retrieve the user ID from the session
    user_id = session.get('user_id')

    # Fetch prediction history for the logged-in user
    prediction_history = PredictionHistory.query.filter_by(user_id=user_id).all()

    # Render the results history template and pass the prediction history
    return render_template('result_hist.html', prediction_history=prediction_history)




@app.route('/recommendationHpb/<float:likelihood>')
def recommendationHpb(likelihood):


    return render_template('recohpb.html', likelihood=likelihood)


    #return render_template('recommendationHpb.html',likelihood=likelihood)


@app.route('/recommendationDia/<float:likelihood>')
def recommendationDia(likelihood):

    return render_template('recommendationDia.html',likelihood=likelihood)

@app.route('/logout')
def logout():
    session.clear()

    # Clear the 'username' cookie
    resp = make_response(redirect(url_for('login')))
    resp.set_cookie('username', '', expires=0)

    flash('You have been logged out.', 'info')
    return resp



if __name__ == '__main__':
    db.create_all()
    app.run(debug=True)