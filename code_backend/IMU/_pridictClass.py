#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
对一条 9 维 IMU 数据做一次分类预测：
python predict_class.py -550 61 933 1525 1098 1647 -27718 18235 -54108
"""
import argparse, os, sys, joblib, numpy as np, torch
from motionClassifier import IMUNet

BASE = os.path.dirname(os.path.abspath(__file__))

def load_resources():
    scaler  = joblib.load(os.path.join(BASE, "scaler.pkl"))
    le      = joblib.load(os.path.join(BASE, "label_encoder.pkl"))
    device  = torch.device("cpu")
    model   = IMUNet(in_dim=9, n_classes=len(le.classes_)).to(device)
    model.load_state_dict(torch.load(os.path.join(BASE, "weights", "best_imu_net.pt"), map_location=device))
    model.eval()
    return model, scaler, le, device

def predict(sample, model, scaler, le, device):
    x_scaled = scaler.transform(np.array(sample, dtype=np.float32).reshape(1, -1))
    t = torch.from_numpy(x_scaled).to(device)
    with torch.no_grad():
        idx = model(t).argmax(dim=1).item()
    return le.inverse_transform([idx])[0]

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Predict motion class from 9-axis IMU sample")
    parser.add_argument("values", type=float, nargs=9,
                        help="a_x a_y a_z g_x g_y g_z m_x m_y m_z")
    args = parser.parse_args()

    model, scaler, le, device = load_resources()
    print(predict(args.values, model, scaler, le, device))
