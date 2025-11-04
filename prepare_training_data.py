#!/usr/bin/env python3
"""
数据预处理脚本，用于准备YOLOv8人脸检测训练数据

该脚本可以帮助您组织和预处理人脸检测训练数据，使其符合YOLOv8训练要求。
"""

import os
import cv2
import shutil
import argparse
import random
from pathlib import Path


def create_directory_structure(base_path):
    """
    创建YOLOv8训练所需的标准目录结构
    
    Args:
        base_path (str): 基础路径
    """
    directories = [
        os.path.join(base_path, "images", "train"),
        os.path.join(base_path, "images", "val"),
        os.path.join(base_path, "labels", "train"),
        os.path.join(base_path, "labels", "val")
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"创建目录: {directory}")


def convert_bbox_to_yolo_format(bbox, img_width, img_height):
    """
    将边界框坐标转换为YOLO格式
    
    Args:
        bbox (tuple): (x_min, y_min, x_max, y_max)
        img_width (int): 图像宽度
        img_height (int): 图像高度
    
    Returns:
        tuple: (x_center, y_center, width, height) 归一化后的坐标
    """
    x_min, y_min, x_max, y_max = bbox
    
    # 计算中心点坐标
    x_center = (x_min + x_max) / 2 / img_width
    y_center = (y_min + y_max) / 2 / img_height
    
    # 计算宽度和高度
    width = (x_max - x_min) / img_width
    height = (y_max - y_min) / img_height
    
    return x_center, y_center, width, height


def process_image_and_label(image_path, label_path, output_base_path, split="train"):
    """
    处理单张图像和对应的标签文件
    
    Args:
        image_path (str): 图像文件路径
        label_path (str): 标签文件路径
        output_base_path (str): 输出基础路径
        split (str): 数据集分割 ("train" 或 "val")
    """
    # 读取图像
    img = cv2.imread(image_path)
    if img is None:
        print(f"警告: 无法读取图像 {image_path}")
        return
    
    img_height, img_width = img.shape[:2]
    
    # 复制图像到输出目录
    output_img_path = os.path.join(output_base_path, "images", split, os.path.basename(image_path))
    shutil.copy2(image_path, output_img_path)
    
    # 处理标签文件
    if os.path.exists(label_path):
        # 读取原始标签
        with open(label_path, 'r') as f:
            lines = f.readlines()
        
        # 转换标签格式
        yolo_labels = []
        for line in lines:
            parts = line.strip().split()
            if len(parts) >= 5:
                # 原始格式: class_id x_min y_min x_max y_max
                class_id = int(parts[0])
                x_min = int(parts[1])
                y_min = int(parts[2])
                x_max = int(parts[3])
                y_max = int(parts[4])
                
                # 转换为YOLO格式
                x_center, y_center, width, height = convert_bbox_to_yolo_format(
                    (x_min, y_min, x_max, y_max), img_width, img_height
                )
                
                # 添加到YOLO标签列表
                yolo_labels.append(f"{class_id} {x_center:.6f} {y_center:.6f} {width:.6f} {height:.6f}")
        
        # 保存YOLO格式标签
        output_label_path = os.path.join(output_base_path, "labels", split, os.path.basename(label_path))
        with open(output_label_path, 'w') as f:
            f.write('\n'.join(yolo_labels))
    else:
        print(f"警告: 标签文件不存在 {label_path}")


def split_dataset(images_dir, labels_dir, output_dir, train_ratio=0.8):
    """
    将数据集分割为训练集和验证集
    
    Args:
        images_dir (str): 图像目录
        labels_dir (str): 标签目录
        output_dir (str): 输出目录
        train_ratio (float): 训练集比例
    """
    # 创建目录结构
    create_directory_structure(output_dir)
    
    # 获取所有图像文件
    image_files = [f for f in os.listdir(images_dir) if f.lower().endswith(('.png', '.jpg', '.jpeg'))]
    
    # 随机打乱文件列表
    random.shuffle(image_files)
    
    # 计算分割点
    split_index = int(len(image_files) * train_ratio)
    
    # 分割为训练集和验证集
    train_files = image_files[:split_index]
    val_files = image_files[split_index:]
    
    print(f"训练集文件数: {len(train_files)}")
    print(f"验证集文件数: {len(val_files)}")
    
    # 处理训练集
    for image_file in train_files:
        image_path = os.path.join(images_dir, image_file)
        label_file = os.path.splitext(image_file)[0] + '.txt'
        label_path = os.path.join(labels_dir, label_file)
        process_image_and_label(image_path, label_path, output_dir, "train")
    
    # 处理验证集
    for image_file in val_files:
        image_path = os.path.join(images_dir, image_file)
        label_file = os.path.splitext(image_file)[0] + '.txt'
        label_path = os.path.join(labels_dir, label_file)
        process_image_and_label(image_path, label_path, output_dir, "val")
    
    print("数据集分割完成!")


def main():
    parser = argparse.ArgumentParser(description="准备YOLOv8人脸检测训练数据")
    parser.add_argument(
        "--images",
        type=str,
        required=True,
        help="原始图像目录路径"
    )
    parser.add_argument(
        "--labels",
        type=str,
        required=True,
        help="原始标签目录路径"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="./models/face_data",
        help="输出目录路径 (默认: ./models/face_data)"
    )
    parser.add_argument(
        "--train-ratio",
        type=float,
        default=0.8,
        help="训练集比例 (默认: 0.8)"
    )
    
    args = parser.parse_args()
    
    try:
        # 检查输入目录是否存在
        if not os.path.exists(args.images):
            raise FileNotFoundError(f"图像目录不存在: {args.images}")
        
        if not os.path.exists(args.labels):
            raise FileNotFoundError(f"标签目录不存在: {args.labels}")
        
        # 分割数据集
        split_dataset(args.images, args.labels, args.output, args.train_ratio)
        
        print(f"数据预处理完成!")
        print(f"处理后的数据保存在: {args.output}")
        print("\n目录结构:")
        print(f"{args.output}/")
        print(f"  ├── images/")
        print(f"  │   ├── train/")
        print(f"  │   └── val/")
        print(f"  └── labels/")
        print(f"      ├── train/")
        print(f"      └── val/")
        
    except Exception as e:
        print(f"数据预处理过程中发生错误: {e}")
        raise


if __name__ == "__main__":
    main()