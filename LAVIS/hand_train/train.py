# train.py
import os
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.neighbors import KNeighborsClassifier
import joblib

class GestureTrainer:
    def __init__(self, data_dir="gesture_data", model_path="gesture_model.pkl"):
        self.data_dir = data_dir
        self.model_path = model_path

    def train(self):
        X, y = [], []

        for file in os.listdir(self.data_dir):
            if file.endswith(".npy"):
                label = file.replace(".npy", "")
                data = np.load(os.path.join(self.data_dir, file))
                X.extend(data)
                y.extend([label] * len(data))

        X = np.array(X)
        y = np.array(y)

        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2)
        model = KNeighborsClassifier(n_neighbors=3)
        model.fit(X_train, y_train)

        accuracy = model.score(X_test, y_test)
        joblib.dump(model, self.model_path)
        print(f"✅ Model trained with accuracy: {accuracy:.2f}")
        print(f"📦 Model saved to: {self.model_path}")

if __name__ == "__main__":
    trainer = GestureTrainer()
    trainer.train()
