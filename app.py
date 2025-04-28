import os
from flask import Flask, request, render_template, redirect, url_for
import tensorflow as tf
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input, decode_predictions
from PIL import Image
import numpy as np
import io

app = Flask(__name__)

# Load the pre-trained MobileNetV2 model + higher level layers
# Load only once when the app starts
try:
    model = MobileNetV2(weights='imagenet')
    print("Model loaded successfully.")
except Exception as e:
    print(f"Error loading model: {e}")
    model = None

# Define allowed image extensions
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def predict_image(image_stream):
    if model is None:
        raise RuntimeError("Model could not be loaded.")

    try:
        # Open the image file from the stream
        img = Image.open(image_stream).convert('RGB') # Ensure image is RGB

        # Resize the image to the size expected by MobileNetV2 (224x224)
        img = img.resize((224, 224))

        # Convert the image to a numpy array
        img_array = tf.keras.preprocessing.image.img_to_array(img)

        # Expand dimensions to match the model's input shape (1, 224, 224, 3)
        img_array_expanded = np.expand_dims(img_array, axis=0)

        # Preprocess the image for MobileNetV2
        processed_img = preprocess_input(img_array_expanded)

        # Make predictions
        predictions = model.predict(processed_img)

        # Decode the predictions to human-readable labels
        # Get the top prediction
        decoded_predictions = decode_predictions(predictions, top=1)[0]

        # Get the label and confidence of the top prediction
        top_prediction = decoded_predictions[0]
        label = top_prediction[1]
        confidence = float(top_prediction[2]) # Convert numpy float to python float

        # Check if the label contains 'person' or related terms
        # ImageNet labels can be specific ('groom', 'bridegroom', 'scuba_diver')
        # We check for common person-related keywords
        person_keywords = ['person', 'man', 'woman', 'child', 'groom', 'bride', 'scuba_diver', 'figure']
        is_human = any(keyword in label.lower() for keyword in person_keywords)

        return is_human, label, confidence

    except Exception as e:
        print(f"Error during prediction: {e}")
        raise ValueError(f"Image processing or prediction failed: {e}")


@app.route('/', methods=['GET', 'POST'])
def index():
    result_text = None
    is_human_result = None
    prediction_label_result = None
    error_message = None

    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            error_message = 'Koi file select nahi ki gayi'
            return render_template('index.html', error=error_message)

        file = request.files['file']

        # If the user does not select a file, the browser submits an
        # empty file without a filename.
        if file.filename == '':
            error_message = 'Koi file select nahi ki gayi'
            return render_template('index.html', error=error_message)

        if file and allowed_file(file.filename):
            try:
                # Read image file stream
                image_stream = io.BytesIO(file.read())
                image_stream.seek(0) # Reset stream position

                # Get prediction
                is_human_pred, label_pred, confidence = predict_image(image_stream)

                is_human_result = is_human_pred
                prediction_label_result = label_pred

                if is_human_result:
                    result_text = f"Yah ek Insaan hai. (Confidence: {confidence:.2f})"
                else:
                    result_text = f"Yah Insaan nahi hai. (Confidence: {confidence:.2f})"

            except Exception as e:
                error_message = f"Classification mein dikkat aa gayi: {str(e)}"
                print(f"Error processing file: {e}") # Log detailed error server-side
        else:
            error_message = 'Invalid file type. Sirf image files (png, jpg, jpeg, gif, webp) allow hain.'

        # Return the template with the result or error
        return render_template('index.html',
                               result=result_text,
                               is_human=is_human_result,
                               prediction_label=prediction_label_result,
                               error=error_message)

    # For GET requests, just render the template
    return render_template('index.html')

# This part is not needed for Vercel deployment but useful for local testing
# if __name__ == '__main__':
#     app.run(debug=True)

# Vercel uses the 'app' variable directly