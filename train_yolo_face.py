#!/usr/bin/env python3
"""
YOLOv8 人脸检测模型训练脚本

该脚本用于训练自定义的人脸检测模型，以提高专注度监测的准确性。
支持GPU加速训练以提高训练速度。
"""

import os
import argparse
import torch
from ultralytics import YOLO


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
        print("CUDA不可用，将使用CPU训练（较慢）")


def create_data_yaml(data_path, class_names):
    """
    创建YOLO训练所需的数据配置文件
    
    Args:
        data_path (str): 数据集根目录路径
        class_names (list): 类别名称列表
    """
    # 创建数据配置文件内容
    data_yaml_content = f"""
# YOLOv8 人脸检测数据配置文件
path: {data_path}  # 数据集根目录
train: images/train  # 训练集图像目录
val: images/val      # 验证集图像目录

# 类别数量
nc: {len(class_names)}

# 类别名称
names: {class_names}
"""
    
    # 保存配置文件
    yaml_path = os.path.join(data_path, "data.yaml")
    with open(yaml_path, "w", encoding="utf-8") as f:
        f.write(data_yaml_content.strip())
    
    print(f"数据配置文件已创建: {yaml_path}")
    return yaml_path


def train_model(
    model_type="yolov8n.pt",
    data_path="./models/face_data",
    epochs=100,
    imgsz=640,
    batch_size=16,
    project="face_training",
    name="face_model",
    device="0",  # 默认使用第一个GPU
    optimizer="AdamW",  # 使用AdamW优化器
    workers=8  # 增加数据加载工作线程数
):
    """
    训练YOLOv8人脸检测模型
    
    Args:
        model_type (str): 预训练模型类型
        data_path (str): 数据集路径
        epochs (int): 训练轮数
        imgsz (int): 图像尺寸
        batch_size (int): 批次大小
        project (str): 项目名称
        name (str): 实验名称
        device (str): 训练设备 (0表示第一个GPU, cpu表示CPU)
        optimizer (str): 优化器类型
        workers (int): 数据加载工作线程数
    """
    print(f"开始训练YOLOv8人脸检测模型...")
    print(f"使用的预训练模型: {model_type}")
    print(f"数据集路径: {data_path}")
    print(f"训练轮数: {epochs}")
    print(f"图像尺寸: {imgsz}")
    print(f"批次大小: {batch_size}")
    print(f"训练设备: {device}")
    print(f"优化器: {optimizer}")
    print(f"工作线程数: {workers}")
    
    # 检查数据集路径是否存在
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"数据集路径不存在: {data_path}")
    
    # 创建数据配置文件
    data_yaml = create_data_yaml(data_path, ["face"])
    
    # 加载预训练模型
    model = YOLO(model_type)
    
    # 开始训练
    model.train(
        data=data_yaml,
        epochs=epochs,
        imgsz=imgsz,
        batch=batch_size,
        project=project,
        name=name,
        device=device,
        optimizer=optimizer,
        workers=workers,
        exist_ok=True,
        # 性能优化参数
        amp=True,  # 自动混合精度训练
        patience=20,  # 早停耐心值
        cos_lr=True,  # 使用余弦退火学习率调度
        close_mosaic=10,  # 最后10个epoch关闭mosaic增强
    )
    
    print(f"模型训练完成!")
    print(f"训练结果保存在: {os.path.join(project, name)}")
    
    # 验证模型
    print("开始验证模型...")
    metrics = model.val()
    print(f"验证完成 - mAP50: {metrics.box.map50}, mAP50-95: {metrics.box.map}")
    
    return model


def export_model(model, format="pt"):
    """
    导出训练好的模型
    
    Args:
        model: 训练好的模型
        format (str): 导出格式
    """
    print(f"导出模型为 {format} 格式...")
    model.export(format=format)
    print(f"模型导出完成!")


def main():
    parser = argparse.ArgumentParser(description="训练YOLOv8人脸检测模型")
    parser.add_argument(
        "--model",
        type=str,
        default="yolov8n.pt",
        help="预训练模型 (默认: yolov8n.pt)"
    )
    parser.add_argument(
        "--data",
        type=str,
        default="./models/face_data",
        help="数据集路径 (默认: ./models/face_data)"
    )
    parser.add_argument(
        "--epochs",
        type=int,
        default=100,
        help="训练轮数 (默认: 100)"
    )
    parser.add_argument(
        "--imgsz",
        type=int,
        default=640,
        help="图像尺寸 (默认: 640)"
    )
    parser.add_argument(
        "--batch",
        type=int,
        default=16,
        help="批次大小 (默认: 16)"
    )
    parser.add_argument(
        "--project",
        type=str,
        default="face_training",
        help="项目名称 (默认: face_training)"
    )
    parser.add_argument(
        "--name",
        type=str,
        default="face_model",
        help="实验名称 (默认: face_model)"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="0" if torch.cuda.is_available() else "cpu",
        help="训练设备 (默认: auto detect)"
    )
    parser.add_argument(
        "--optimizer",
        type=str,
        default="AdamW",
        help="优化器 (默认: AdamW)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=8,
        help="数据加载工作线程数 (默认: 8)"
    )
    
    args = parser.parse_args()
    
    # 检查CUDA可用性
    check_cuda_availability()
    
    try:
        # 训练模型
        model = train_model(
            model_type=args.model,
            data_path=args.data,
            epochs=args.epochs,
            imgsz=args.imgsz,
            batch_size=args.batch,
            project=args.project,
            name=args.name,
            device=args.device,
            optimizer=args.optimizer,
            workers=args.workers
        )
        
        # 导出模型
        export_model(model)
        
        print("训练流程完成!")
        print(f"最终模型保存在: {os.path.join(args.project, args.name, 'weights')}")
        
    except Exception as e:
        print(f"训练过程中发生错误: {e}")
        raise


if __name__ == "__main__":
    main()