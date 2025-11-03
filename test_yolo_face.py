#!/usr/bin/env python3
"""
YOLOv8 人脸检测模型测试脚本

该脚本用于测试训练好的人脸检测模型的性能。
支持GPU加速推理以提高测试速度。
"""

import cv2
import torch
import numpy as np
from ultralytics import YOLO
import argparse
import os


def check_cuda_availability():
    """
    检查CUDA可用性并打印相关信息
    """
    print("检查CUDA和GPU可用性...")
    print(f"CUDA可用: {torch.cuda.is_available()}")
    print(f"GPU数量: {torch.cuda.device_count()}")
    
    if torch.cuda.is_available():
        print(f"当前GPU: {torch.cuda.get_device_name()}")
        print(f"CUDA版本: {torch.version.cuda}")
    else:
        print("CUDA不可用，将使用CPU推理（较慢）")


def test_image(model, image_path, conf_threshold=0.5, device="cpu"):
    """
    在单张图像上测试模型
    
    Args:
        model: 训练好的YOLO模型
        image_path (str): 图像路径
        conf_threshold (float): 置信度阈值
        device (str): 推理设备
    """
    # 检查图像文件是否存在
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"图像文件不存在: {image_path}")
    
    # 读取图像
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f"无法读取图像: {image_path}")
    
    # 使用模型进行预测
    results = model(image, conf=conf_threshold, device=device)
    
    # 获取检测结果
    detections = results[0].boxes
    
    # 在图像上绘制检测框
    for box in detections:
        # 获取边界框坐标
        x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
        conf = box.conf[0].cpu().numpy()
        cls = int(box.cls[0].cpu().numpy())
        
        # 绘制边界框
        cv2.rectangle(image, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
        
        # 添加标签
        label = f"Face {conf:.2f}"
        cv2.putText(image, label, (int(x1), int(y1 - 10)), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
    
    # 保存结果图像
    output_path = image_path.replace(".", "_result.")
    cv2.imwrite(output_path, image)
    print(f"检测结果已保存到: {output_path}")
    
    return len(detections)


def test_webcam(model, conf_threshold=0.5, device="cpu"):
    """
    使用摄像头实时测试模型
    
    Args:
        model: 训练好的YOLO模型
        conf_threshold (float): 置信度阈值
        device (str): 推理设备
    """
    # 打开摄像头
    cap = cv2.VideoCapture(0)
    
    if not cap.isOpened():
        raise ValueError("无法打开摄像头")
    
    print("按 'q' 键退出摄像头测试")
    
    while True:
        # 读取帧
        ret, frame = cap.read()
        if not ret:
            break
        
        # 使用模型进行预测
        results = model(frame, conf=conf_threshold, device=device, verbose=False)
        
        # 获取检测结果
        detections = results[0].boxes
        
        # 在帧上绘制检测框
        for box in detections:
            # 获取边界框坐标
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            conf = box.conf[0].cpu().numpy()
            cls = int(box.cls[0].cpu().numpy())
            
            # 绘制边界框
            cv2.rectangle(frame, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            
            # 添加标签
            label = f"Face {conf:.2f}"
            cv2.putText(frame, label, (int(x1), int(y1 - 10)), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 0), 2)
        
        # 显示帧
        cv2.imshow('YOLOv8 Face Detection', frame)
        
        # 按 'q' 键退出
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break
    
    # 释放资源
    cap.release()
    cv2.destroyAllWindows()
    print("摄像头测试结束")


def evaluate_model(model, data_path, conf_threshold=0.5, device="cpu"):
    """
    评估模型在验证集上的性能
    
    Args:
        model: 训练好的YOLO模型
        data_path (str): 数据集路径
        conf_threshold (float): 置信度阈值
        device (str): 推理设备
    """
    print("开始评估模型性能...")
    
    # 验证模型
    metrics = model.val(data=os.path.join(data_path, "data.yaml"), conf=conf_threshold, device=device)
    
    print(f"模型评估结果:")
    print(f"  mAP50: {metrics.box.map50:.4f}")
    print(f"  mAP50-95: {metrics.box.map:.4f}")
    print(f"  Precision: {metrics.box.p:.4f}")
    print(f"  Recall: {metrics.box.r:.4f}")
    print(f"  F1-Score: {metrics.box.f1:.4f}")


def main():
    parser = argparse.ArgumentParser(description="测试YOLOv8人脸检测模型")
    parser.add_argument(
        "--model",
        type=str,
        required=True,
        help="训练好的模型路径 (例如: best.pt)"
    )
    parser.add_argument(
        "--image",
        type=str,
        help="测试图像路径"
    )
    parser.add_argument(
        "--webcam",
        action="store_true",
        help="使用摄像头进行实时测试"
    )
    parser.add_argument(
        "--eval",
        action="store_true",
        help="评估模型在验证集上的性能"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="./models/face_data",
        help="数据集路径 (默认: ./models/face_data)"
    )
    parser.add_argument(
        "--conf",
        type=float,
        default=0.5,
        help="置信度阈值 (默认: 0.5)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="0" if torch.cuda.is_available() else "cpu",
        help="推理设备 (默认: auto detect)"
    )
    
    args = parser.parse_args()
    
    # 检查CUDA可用性
    check_cuda_availability()
    
    try:
        # 加载模型
        print(f"加载模型: {args.model}")
        model = YOLO(args.model)
        print("模型加载成功!")
        
        # 根据参数执行不同测试
        if args.image:
            count = test_image(model, args.image, args.conf, args.device)
            print(f"在图像中检测到 {count} 张人脸")
        elif args.webcam:
            test_webcam(model, args.conf, args.device)
        elif args.eval:
            evaluate_model(model, args.data, args.conf, args.device)
        else:
            print("请指定测试模式: --image, --webcam, 或 --eval")
            
    except Exception as e:
        print(f"测试过程中发生错误: {e}")
        raise


if __name__ == "__main__":
    main()