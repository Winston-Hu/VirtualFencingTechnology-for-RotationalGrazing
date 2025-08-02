import os
import random
import numpy as np
import pandas as pd
from tqdm import tqdm
import joblib

from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

BASE = os.path.dirname(os.path.abspath(__file__))
WEIGHTS_DIR = os.path.join(BASE, "weights")
os.makedirs(WEIGHTS_DIR, exist_ok=True)

CSV_PATH = "dataset/imu_data_test.csv"
BATCH_SIZE_TR = 64
BATCH_SIZE_EVAL = 256
EPOCHS = 50
PATIENCE = 6
LEARNING_RATE = 1e-3
WEIGHT_DECAY = 1e-4
DROPOUT_P = 0.3
VAL_RATIO = 0.15
TEST_RATIO = 0.15
RANDOM_SEED = 42


def set_seed(seed=RANDOM_SEED):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)


set_seed()


class IMUDataset(Dataset):
    def __init__(self, X, y):
        self.X = torch.tensor(X, dtype=torch.float32)
        self.y = torch.tensor(y, dtype=torch.long)

    def __len__(self):
        return self.X.shape[0]

    def __getitem__(self, idx):
        return self.X[idx], self.y[idx]


class IMUNet(nn.Module):
    def __init__(self, in_dim=9, n_classes=5, p=DROPOUT_P):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(in_dim, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(p),
            nn.Linear(128, 64),
            nn.ReLU(),
            nn.Dropout(p),
            nn.Linear(64, n_classes)
        )

    def forward(self, x):
        return self.net(x)


def train_and_save():
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"🖥  Using device: {device}")

    assert os.path.exists(CSV_PATH), f"找不到 {CSV_PATH}"
    df = pd.read_csv(CSV_PATH)
    print(df.shape)
    assert df.shape[1] == 10, "CSV 应有 10 列 (9 特征 + class_name)"

    X = df.drop(columns=["class_name"]).values.astype(np.float32)
    y = df["class_name"].values

    le = LabelEncoder()
    y_enc = le.fit_transform(y)
    n_classes = len(le.classes_)
    print("类别映射:", dict(zip(le.classes_, le.transform(le.classes_))))

    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y_enc, test_size=VAL_RATIO + TEST_RATIO,
        stratify=y_enc, random_state=RANDOM_SEED)

    val_size = VAL_RATIO / (VAL_RATIO + TEST_RATIO)
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=1 - val_size,
        stratify=y_temp, random_state=RANDOM_SEED)

    print(f"📊 数据集规模  train:{len(X_train)}  val:{len(X_val)}  test:{len(X_test)}")

    scaler = StandardScaler().fit(X_train)
    X_train = scaler.transform(X_train)
    X_val = scaler.transform(X_val)
    X_test = scaler.transform(X_test)

    train_dl = DataLoader(IMUDataset(X_train, y_train),
                          batch_size=BATCH_SIZE_TR, shuffle=True)
    val_dl = DataLoader(IMUDataset(X_val, y_val),
                        batch_size=BATCH_SIZE_EVAL)
    test_dl = DataLoader(IMUDataset(X_test, y_test),
                         batch_size=BATCH_SIZE_EVAL)

    model = IMUNet(in_dim=9, n_classes=n_classes).to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = torch.optim.Adam(model.parameters(),
                                 lr=LEARNING_RATE, weight_decay=WEIGHT_DECAY)

    best_val_acc, wait = 0.0, 0
    for epoch in range(1, EPOCHS + 1):
        # ---- 训练 ----
        model.train()
        running_loss = 0.0
        samples_count = 0

        pbar = tqdm(
            train_dl,
            desc=f"Epoch {epoch:02d}",
            unit="batch",
            leave=False
        )
        for xb, yb in pbar:
            xb, yb = xb.to(device), yb.to(device)
            optimizer.zero_grad()
            logits = model(xb)
            loss = criterion(logits, yb)
            loss.backward()
            optimizer.step()

            batch_size = yb.size(0)
            running_loss += loss.item() * yb.size(0)
            samples_count += batch_size
            avg_loss = running_loss / samples_count
            pbar.set_postfix(train_loss=f"{avg_loss:.4f}")

        pbar.close()

        model.eval()
        correct, total = 0, 0
        with torch.no_grad():
            for xb, yb in val_dl:
                xb, yb = xb.to(device), yb.to(device)
                preds = model(xb).argmax(dim=1)
                correct += (preds == yb).sum().item()
                total += yb.size(0)
        val_acc = correct / total
        tqdm.write(
            f"[{epoch:02d}] train_loss={running_loss / len(X_train):.4f} "
            f"val_acc={val_acc:.4f}"
        )

        if val_acc > best_val_acc:
            best_val_acc = val_acc
            torch.save(model.state_dict(), os.path.join(WEIGHTS_DIR, "best_imu_net.pt"))
            wait = 0
        else:
            wait += 1
            if wait >= PATIENCE:
                print("Early stopping triggered.")
                break

    torch.save(model.state_dict(), "weights/best_imu_net.pt")
    joblib.dump(scaler, os.path.join(BASE, "weights/scaler.pkl"))
    joblib.dump(le, os.path.join(BASE, "weights/label_encoder.pkl"))
    print("✅ 已保存权重、scaler 和 label_encoder")
    print(f"✅ 训练结束，最佳验证准确率 {best_val_acc:.4f}")
    model.load_state_dict(torch.load("weights/best_imu_net.pt"))

    model.eval()
    all_true, all_pred = [], []
    with torch.no_grad():
        for xb, yb in test_dl:
            xb = xb.to(device)
            probs = model(xb).softmax(dim=1)
            preds = probs.argmax(dim=1).cpu().numpy()
            all_pred.extend(preds)
            all_true.extend(yb.numpy())

    print("\n=== Classification Report (test set) ===")
    print(classification_report(all_true, all_pred, target_names=le.classes_))

    print("=== Confusion Matrix ===")
    print(confusion_matrix(all_true, all_pred))


if __name__ == "__main__":
    train_and_save()
