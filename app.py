from flask import Flask, jsonify

# Vercel MUST see a top-level variable named "app"
app = Flask(__name__)

@app.route("/")
def home():
    return jsonify({"status": "success", "message": "DeepAir API is live on Vercel!"})

# Optional extra route (you can add your AI model here later)
@app.route("/predict")
def predict():
    return jsonify({"prediction": "Demo output"})


# Local development runner (ignored by Vercel)
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
