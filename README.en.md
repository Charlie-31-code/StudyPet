# StudyPet

English | [简体中文](README.md)

## Project Introduction

StudyPet is a learning companion (partner) designed for college students, based on the [py-xiaozhi](https://github.com/huangjunsen0406/py-xiaozhi) project as a secondary development. This project helps college students improve their learning focus through AI technology, providing voice interaction and visual monitoring functions.

## Features

### 🎯 Core AI Capabilities

- **AI Voice Interaction**: Supports voice input and recognition, enabling intelligent human-computer interaction with natural conversation flow
- **Visual Multimodal**: Supports image recognition and processing, providing multimodal interaction capabilities and image content understanding
- **Intelligent Wake-up**: Supports multiple wake word activation for hands-free interaction (configurable)
- **Continuous Dialogue Mode**: Implements seamless conversation experience, enhancing user interaction fluidity
- **YOLO Face Detection**: Integrated YOLO deep learning model for high-precision face detection and focus analysis with real-time user status monitoring. Analyzes face position, size, and angle to determine user focus, providing more accurate learning status monitoring

### 🔧 MCP Tools Ecosystem

- **System Control Tools**: System status monitoring, application management, volume control, device management
- **Calendar Management Tools**: Full-featured calendar system with create, query, update, delete events, intelligent categorization and reminders
- **Timer Tools**: Countdown timer functionality with delayed MCP tool execution and parallel task management
- **Music Player Tools**: Online music search and playback with playback controls, lyrics display, and local cache management
- **Search Tools**: Web search and content retrieval with Bing search integration and intelligent content parsing
- **Recipe Tools**: Rich recipe database with search, category browsing, and intelligent recommendations
- **Camera Tools**: Image capture and AI analysis with photo recognition and intelligent Q&A
- **YOLO Vision Analysis**: Face detection and focus monitoring based on YOLO model for learning efficiency evaluation and user status perception. Supports training custom models to improve detection accuracy and adapt to different usage scenarios

### 🎵 Advanced Audio Processing

- **Multi-level Audio Processing**: Supports Opus codec and real-time resampling
- **Voice Activity Detection**: VAD detector for intelligent interruption with real-time voice activity monitoring
- **Wake Word Detection**: Sherpa-ONNX-based offline speech recognition with multiple wake words and pinyin matching
- **Audio Stream Management**: Independent input/output streams with stream rebuild and error recovery
- **Audio Echo Cancellation**: Integrated WebRTC audio processing module providing high-quality echo cancellation
- **System Audio Recording**: Supports system audio recording with audio loopback processing

### 🖥️ User Interface

- **Graphical Interface**: Modern PyQt5-based GUI with Xiaozhi expressions and text display for enhanced visual experience
- **Command Line Mode**: CLI support suitable for embedded devices or GUI-less environments
- **System Tray**: Background operation support with integrated system tray functionality
- **Global Hotkeys**: Global hotkey support for improved usability
- **Settings Interface**: Complete settings management interface with configuration customization

### 🔒 Security & Stability

- **Encrypted Audio Transmission**: WSS protocol support ensuring audio data security and preventing information leakage
- **Device Activation System**: Dual v1/v2 protocol activation with automatic verification code and device fingerprint handling
- **Error Recovery**: Complete error handling and recovery mechanisms with reconnection support

### 🌐 Cross-platform Support

- **System Compatibility**: Compatible with Windows 10+, macOS 10.15+, and Linux systems
- **Protocol Support**: WebSocket and MQTT dual protocol communication support
- **Multi-environment Deployment**: GUI and CLI dual modes adapting to different deployment environments
- **Platform Optimization**: Audio and system control optimization for different platforms

## YOLOv8 Face Detection Enhanced Features

To improve the accuracy of focus monitoring, the project integrates an advanced YOLOv8 face detection model. This model can more accurately identify face position, size, and angle, thus more accurately judging the user's focus status.

### Features

- **High-Precision Detection**: Uses a specially trained YOLOv8 face detection model
- **Real-Time Monitoring**: Supports real-time face detection and focus analysis
- **GPU Acceleration**: Supports CUDA GPU acceleration to improve detection speed
- **Multiple State Recognition**:
  - `focused`: Face detected and located in the center area of the frame with reasonable size and angle
  - `distracted`: Face detected but position deviates from center or angle is abnormal
  - `absent`: No face detected
  - `blocked`: Camera blocked or frame too dark

### Model Training

The project provides complete model training scripts that support training with custom datasets:

1. Prepare annotated face dataset (YOLO format)
2. Use the [train_yolo_face.py](train_yolo_face.py) script for model training
3. Supports GPU-accelerated training to significantly improve training speed
4. Uses `yolov8n.pt` as the default pre-trained model

### Model Testing

Provides test scripts to verify model performance:

1. Use the [test_yolo_face.py](test_yolo_face.py) script to test the trained model
2. Supports image file and real-time camera testing
3. Supports GPU-accelerated inference

### Face Focus Determination Logic

The system determines user focus status based on the following factors:

- Face position: Whether it is located in the center area of the frame
- Size ratio: The ratio of face size to expected size
- Aspect ratio: Determine if the face is front-facing
- Lighting conditions: Detect if the frame is too dark or blocked

## Technical Architecture

### Core Architecture Design

- **Event-Driven Architecture**: Based on asyncio asynchronous event loop, supporting high-concurrency processing
- **Layered Design**: Clear separation of application layer, protocol layer, device layer, and UI layer
- **Singleton Pattern**: Core components use singleton pattern to ensure unified resource management
- **Plugin System**: MCP tool system and IoT devices support plugin-based extension

### Key Technical Components

- **Audio Processing**: Opus codec, WebRTC echo cancellation, real-time resampling, system audio recording
- **Speech Recognition**: Sherpa-ONNX offline models, voice activity detection, wake word recognition
- **Protocol Communication**: WebSocket/MQTT dual protocol support, encrypted transmission, auto-reconnection
- **Configuration System**: Hierarchical configuration, dot notation access, dynamic updates, JSON/YAML support

### Performance Optimization

- **Async First**: Full system asynchronous architecture, avoiding blocking operations
- **Memory Management**: Smart caching, garbage collection
- **Audio Optimization**: 5ms low-latency processing, queue management, streaming transmission
- **Concurrency Control**: Task pool management, semaphore control, thread safety

### Security Mechanisms

- **Encrypted Communication**: WSS/TLS encryption, certificate verification
- **Device Authentication**: Dual protocol activation, device fingerprint recognition
- **Access Control**: Tool permission management, API access control
- **Error Isolation**: Exception isolation, fault recovery, graceful degradation

## Development Guide

### Project Structure

```
StudyPet-4/
├── main.py                     # Application main entry (CLI argument handling)
├── src/
│   ├── application.py          # Application core logic
│   ├── audio_codecs/           # Audio codecs
│   │   ├── aec_processor.py    # Audio echo cancellation processor
│   │   ├── audio_codec.py      # Audio codec base class
│   ├── audio_processing/       # Audio processing modules
│   │   ├── vad_detector.py     # Voice activity detection
│   │   └── wake_word_detect.py # Wake word detection
│   ├── constants/              # Constant definitions
│   ├── core/                   # Core components
│   │   ├── ota.py             # Over-the-air update module
│   │   └── system_initializer.py # System initializer
│   ├── display/                # Display interface abstraction layer
│   ├── mcp/                    # MCP tool system
│   │   ├── mcp_server.py      # MCP server
│   │   └── tools/             # Various tool modules
│   │       ├── calendar/      # Calendar tools
│   │       ├── camera/        # Camera tools
│   │       ├── music/         # Music player tools
│   │       ├── screenshot/     # Screenshot tools
│   │       ├── system/        # System tools
│   │       └── timer/         # Timer tools
│   ├── network/                # Network communication module
│   ├── plugins/                # Plugin system
│   ├── protocols/              # Communication protocols
│   ├── study/                  # Study and focus modules
│   │   ├── face.py            # Face focus monitor (supports Haar Cascade and YOLO)
│   │   └── tomato.py          # Pomodoro timer
│   ├── utils/                  # Utility functions
│   └── views/                  # UI view components
├── libs/                       # Third-party native libraries
│   └── webrtc_apm/            # WebRTC audio processing module
├── config/                     # Configuration file directory
├── models/                     # Model files directory
│   ├── yolov8n.pt             # YOLOv8 pre-trained face detection model
│   └── yolo11n.pt             # YOLO11 pre-trained face detection model
├── assets/                     # Static resource files
├── scripts/                    # Auxiliary scripts
├── requirements.txt            # Python dependency package list
└── pyproject.toml             # Project configuration file
```

### Development Environment Setup

```bash
# Clone project
git clone https://github.com/huangjunsen0406/py-xiaozhi.git
cd py-xiaozhi

# Install dependencies
pip install -r requirements.txt

# Install YOLOv8 for advanced computer vision capabilities
pip install ultralytics

# The project already includes pre-trained model files:
# - yolov8n.pt: Lightweight YOLOv8 model suitable for real-time detection
# - yolo11n.pt: YOLO11 model providing higher accuracy detection

# Code formatting
./format_code.sh

# Run program - GUI mode (default)
python main.py

# Run program - CLI mode
python main.py --mode cli

# Specify communication protocol
python main.py --protocol websocket  # WebSocket (default)
python main.py --protocol mqtt       # MQTT protocol
```

### Core Development Patterns

- **Async First**: Use `async/await` syntax, avoid blocking operations
- **Error Handling**: Complete exception handling and logging
- **Configuration Management**: Use `ConfigManager` unified configuration access
- **Test Driven**: Write unit tests to ensure code quality

### Extension Development

- **Add MCP Tools**: Create new tool modules in `src/mcp/tools/` directory
- **Add Interfaces**: Extend `BaseDisplay` to implement new UI components

### State Transition Diagram

```
                        +----------------+
                        |                |
                        v                |
+------+  Wake/Button  +------------+   |   +------------+
| IDLE | -----------> | CONNECTING | --+-> | LISTENING  |
+------+              +------------+       +------------+
   ^                                            |
   |                                            | Voice Recognition Complete
   |          +------------+                    v
   +--------- |  SPEAKING  | <-----------------+
     Playback +------------+
     Complete
```

## System Requirements

### Basic Requirements

- **Python Version**: 3.9 - 3.12
- **Operating System**: Windows 10+, macOS 10.15+, Linux
- **Audio Devices**: Microphone and speaker devices
- **Network Connection**: Stable internet connection (for AI services and online features)

### Recommended Configuration

- **Memory**: At least 4GB RAM (8GB+ recommended)
- **Processor**: Modern CPU with AVX instruction set support
- **Storage**: At least 2GB available disk space (for model files and cache)
- **Audio**: Audio devices supporting 16kHz sampling rate

### Optional Feature Requirements

- **Voice Wake-up**: Requires downloading Sherpa-ONNX speech recognition models
- **Camera Features**: Requires camera device and OpenCV support
- **YOLO Face Detection**: Requires installing YOLO-related dependencies for improved face detection accuracy