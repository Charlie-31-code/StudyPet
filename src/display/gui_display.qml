import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtGraphicalEffects 1.15

Rectangle {
    id: root
    width: 800
    height: 500
    color: "#f5f5f5"

    // 信号定义 - 与 Python 回调对接
    signal manualButtonPressed()
    signal manualButtonReleased()
    signal autoButtonClicked()
    signal abortButtonClicked()
    signal modeButtonClicked()
    signal sendButtonClicked(string text)
    signal settingsButtonClicked()
    signal studyModeClicked()
    signal studyStartClicked()
    signal studyStartAlreadyClicked()
    signal studyStopClicked()
    // 标题栏相关信号
    signal titleMinimize()
    signal titleClose()
    signal titleDragStart(real mouseX, real mouseY)
    signal titleDragMoveTo(real mouseX, real mouseY)
    signal titleDragEnd()

    // 主布局
    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 0
        spacing: 0

        // 自定义标题栏：最小化、关闭、可拖动
        Rectangle {
            id: titleBar
            Layout.fillWidth: true
            Layout.preferredHeight: 36
            color: "#f7f8fa"
            border.width: 0

            // 整条标题栏拖动（使用屏幕坐标，避免累计误差导致抖动）
            // 放在最底层，让按钮的 MouseArea 可以优先响应
            MouseArea {
                anchors.fill: parent
                acceptedButtons: Qt.LeftButton
                onPressed: {
                    root.titleDragStart(mouse.x, mouse.y)
                }
                onPositionChanged: {
                    if (pressed) {
                        root.titleDragMoveTo(mouse.x, mouse.y)
                    }
                }
                onReleased: {
                    root.titleDragEnd()
                }
                z: 0  // 最底层
            }

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 10
                anchors.rightMargin: 8
                spacing: 8
                z: 1  // 按钮层在拖动层上方

                // 左侧拖动区域
                Item { id: dragArea; Layout.fillWidth: true; Layout.fillHeight: true }

                // 最小化
                Rectangle {
                    id: btnMin
                    width: 24; height: 24; radius: 6
                    color: btnMinMouse.pressed ? "#e5e6eb" : (btnMinMouse.containsMouse ? "#f2f3f5" : "transparent")
                    z: 2  // 确保按钮在最上层
                    Text { anchors.centerIn: parent; text: "–"; font.pixelSize: 14; color: "#4e5969" }
                    MouseArea {
                        id: btnMinMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleMinimize()
                    }
                }

                // 关闭
                Rectangle {
                    id: btnClose
                    width: 24; height: 24; radius: 6
                    color: btnCloseMouse.pressed ? "#f53f3f" : (btnCloseMouse.containsMouse ? "#ff7875" : "transparent")
                    z: 2  // 确保按钮在最上层
                    Text { anchors.centerIn: parent; text: "×"; font.pixelSize: 14; color: btnCloseMouse.containsMouse ? "white" : "#86909c" }
                    MouseArea {
                        id: btnCloseMouse
                        anchors.fill: parent
                        hoverEnabled: true
                        onClicked: root.titleClose()
                    }
                }
            }
        }

        // 状态卡片区域
        Rectangle {
            id: statusCard
            Layout.fillWidth: true
            Layout.fillHeight: true
            color: "transparent"

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: 20
                spacing: 20

                // 状态标签
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 48
                    color: "#E3F2FD"
                    radius: 12

                    Text {
                        anchors.centerIn: parent
                        text: displayModel ? displayModel.statusText : "状态: 未连接"
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 14
                        font.weight: Font.Bold
                        color: "#2196F3"
                    }
                }

                // 表情显示区域
                Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    Layout.minimumHeight: 120

                    // 动态加载表情：AnimatedImage 用于 GIF，Image 用于静态图，Text 用于 emoji
                    Loader {
                        id: emotionLoader
                        anchors.centerIn: parent
                        // 保持正方形，取宽高中较小值的 85%
                        property real maxSize: Math.min(parent.width, parent.height) * 0.85
                        width: maxSize
                        height: maxSize

                        sourceComponent: {
                            var path = displayModel ? displayModel.emotionPath : ""
                            if (!path || path.length === 0) {
                                return emojiComponent
                            }
                            if (path.indexOf(".gif") !== -1) {
                                return gifComponent
                            }
                            if (path.indexOf(".") !== -1) {
                                return imageComponent
                            }
                            return emojiComponent
                        }

                        // GIF 动图组件
                        Component {
                            id: gifComponent
                            AnimatedImage {
                                fillMode: Image.PreserveAspectCrop
                                source: displayModel ? displayModel.emotionPath : ""
                                playing: true
                                speed: 1.05
                                cache: true
                                clip: true
                                onStatusChanged: {
                                    if (status === Image.Error) {
                                        console.error("AnimatedImage error:", errorString, "src=", source)
                                    }
                                }
                            }
                        }

                        // 静态图片组件
                        Component {
                            id: imageComponent
                            Image {
                                fillMode: Image.PreserveAspectCrop
                                source: displayModel ? displayModel.emotionPath : ""
                                cache: true
                                clip: true
                                onStatusChanged: {
                                    if (status === Image.Error) {
                                        console.error("Image error:", errorString, "src=", source)
                                    }
                                }
                            }
                        }

                        // Emoji 文本组件
                        Component {
                            id: emojiComponent
                            Text {
                                text: displayModel ? displayModel.emotionPath : "😊"
                                font.pixelSize: 80
                                horizontalAlignment: Text.AlignHCenter
                                verticalAlignment: Text.AlignVCenter
                            }
                        }
                    }
                }

                // TTS 文本显示区域
                Rectangle {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 80
                    color: "transparent"

                    Text {
                        anchors.fill: parent
                        anchors.margins: 15
                        text: displayModel ? displayModel.ttsText : "待命"
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 14
                        color: "#555555"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }

        // 按钮区域（统一配色与尺寸）
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 72
            color: "#f7f8fa"

            RowLayout {
                anchors.fill: parent
                anchors.leftMargin: 16
                anchors.rightMargin: 16
                anchors.bottomMargin: 12
                spacing: 10

                // 手动模式按钮（按住说话） - 主色
                Button {
                    id: manualBtn
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: 40
                    text: "按住后说话"
                    visible: displayModel ? !displayModel.autoMode : true

                    background: Rectangle {
                        color: manualBtn.pressed ? "#0e42d2" : (manualBtn.hovered ? "#4080ff" : "#165dff")
                        radius: 8

                        Behavior on color { ColorAnimation { duration: 120; easing.type: Easing.OutCubic } }
                    }

                    contentItem: Text {
                        text: manualBtn.text
                        font.family: "PingFang SC, Microsoft YaHei UI"
                        font.pixelSize: 13
                        color: "white"
                        horizontalAlignment: Text.AlignHCenter
                        verticalAlignment: Text.AlignVCenter
                    }

                    onPressed: { manualBtn.text = "松开以停止"; root.manualButtonPressed() }
                    onReleased: { manualBtn.text = "按住后说话"; root.manualButtonReleased() }
                }

                // 自动模式按钮 - 主色
                Button {
                    id: autoBtn
                    Layout.preferredWidth: 140
                    Layout.preferredHeight: 40
                    text: displayModel ? displayModel.buttonText : "开始对话"
                    visible: displayModel ? displayModel.autoMode : false

                    background: Rectangle {
                        color: autoBtn.pressed ? "#0e42d2" : (autoBtn.hovered ? "#4080ff" : "#165dff")
                        radius: 8
                        Behavior on color { ColorAnimation { duration: 120; easing.type: Easing.OutCubic } }
                    }

                    contentItem: Text { text: autoBtn.text; font.family: "PingFang SC, Microsoft YaHei UI"; font.pixelSize: 13; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: root.autoButtonClicked()
                }

                // 打断对话 - 次要色
                Button {
                    id: abortBtn
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 40
                    text: "打断对话"

                    background: Rectangle { color: abortBtn.pressed ? "#e5e6eb" : (abortBtn.hovered ? "#f2f3f5" : "#eceff3"); radius: 8 }
                    contentItem: Text { text: abortBtn.text; font.family: "PingFang SC, Microsoft YaHei UI"; font.pixelSize: 13; color: "#1d2129"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: root.abortButtonClicked()
                }

                // 输入 + 发送
                RowLayout {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 40
                    spacing: 8

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: 40
                        color: "white"
                        radius: 8
                        border.color: textInput.activeFocus ? "#165dff" : "#e5e6eb"
                        border.width: 1

                        TextInput {
                            id: textInput
                            anchors.fill: parent
                            anchors.leftMargin: 12
                            anchors.rightMargin: 12
                            verticalAlignment: TextInput.AlignVCenter
                            font.family: "PingFang SC, Microsoft YaHei UI"
                            font.pixelSize: 13
                            color: "#333333"
                            selectByMouse: true
                            clip: true

                            // 占位符
                            Text { anchors.fill: parent; text: "输入文字..."; font: textInput.font; color: "#c9cdd4"; verticalAlignment: Text.AlignVCenter; visible: !textInput.text && !textInput.activeFocus }

                            Keys.onReturnPressed: { if (textInput.text.trim().length > 0) { root.sendButtonClicked(textInput.text); textInput.text = "" } }
                        }
                    }

                    Button {
                        id: sendBtn
                        Layout.preferredWidth: 84
                        Layout.preferredHeight: 40
                        text: "发送"
                        background: Rectangle { color: sendBtn.pressed ? "#0e42d2" : (sendBtn.hovered ? "#4080ff" : "#165dff"); radius: 8 }
                        contentItem: Text { text: sendBtn.text; font.family: "PingFang SC, Microsoft YaHei UI"; font.pixelSize: 13; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                        onClicked: { if (textInput.text.trim().length > 0) { root.sendButtonClicked(textInput.text); textInput.text = "" } }
                    }
                }

                // 模式（次要）
                Button {
                    id: modeBtn
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 40
                    text: displayModel ? displayModel.modeText : "手动对话"
                    background: Rectangle { color: modeBtn.pressed ? "#e5e6eb" : (modeBtn.hovered ? "#f2f3f5" : "#eceff3"); radius: 8 }
                    contentItem: Text { text: modeBtn.text; font.family: "PingFang SC, Microsoft YaHei UI"; font.pixelSize: 13; color: "#1d2129"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: root.modeButtonClicked()
                }

                // 设置（次要）
                Button {
                    id: settingsBtn
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 40
                    text: "参数配置"
                    background: Rectangle { color: settingsBtn.pressed ? "#e5e6eb" : (settingsBtn.hovered ? "#f2f3f5" : "#eceff3"); radius: 8 }
                    contentItem: Text { text: settingsBtn.text; font.family: "PingFang SC, Microsoft YaHei UI"; font.pixelSize: 13; color: "#1d2129"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: root.settingsButtonClicked()
                }

                // 学习模式入口
                Button {
                    id: studyBtn
                    Layout.preferredWidth: 120
                    Layout.preferredHeight: 40
                    text: "学习模式"
                    background: Rectangle { color: studyBtn.pressed ? "#e5e6eb" : (studyBtn.hovered ? "#f2f3f5" : "#eceff3"); radius: 8 }
                    contentItem: Text { text: studyBtn.text; font.family: "PingFang SC, Microsoft YaHei UI"; font.pixelSize: 13; color: "#1d2129"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                    onClicked: root.studyModeClicked()
                }
            }
        }
    }

    // 学习模式覆盖页（浮层）
    Rectangle {
        id: studyOverlay
        anchors.fill: parent
        color: "#ffffffcc"
        visible: displayModel ? displayModel.studyModeActive : false
        z: 20

        ColumnLayout {
            id: studyColumn
            Layout.alignment: Qt.AlignHCenter
            spacing: 16
            width: parent.width * 0.8

            // 主横向布局：左侧宠物/表情，右侧计时/人脸/进度/按钮
            RowLayout {
                Layout.alignment: Qt.AlignHCenter
                spacing: 20
                Layout.preferredWidth: parent.width

                // 左侧：宠物图/表情（较大）
                Image {
                    id: studyPetImg
                    source: displayModel ? displayModel.emotionPath : ""
                    fillMode: Image.PreserveAspectFit
                    Layout.preferredWidth: parent.width * 0.35
                    Layout.preferredHeight: parent.width * 0.35
                }

                // 右侧：计时与人脸窗口等
                ColumnLayout {
                    Layout.preferredWidth: parent.width * 0.45
                    spacing: 12

                    // 计时文案
                    Text {
                        id: timerText
                        text: displayModel ? displayModel.studyTimerText : "25:00"
                        font.pixelSize: 56
                        horizontalAlignment: Text.AlignHCenter
                        Layout.alignment: Qt.AlignHCenter
                        color: "#222222"
                    }

                    // 自定义番茄计时设置（预设 + 手动分钟）
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 8
                        // 预设下拉
                        ComboBox {
                            id: presetCombo
                            model: ["default", "deep", "short"]
                            currentIndex: displayModel ? (displayModel.preset === "deep" ? 1 : (displayModel.preset === "short" ? 2 : 0)) : 0
                            onCurrentTextChanged: {
                                if (displayModel) {
                                    displayModel.preset = currentText
                                    if (currentText === "deep") {
                                        displayModel.studyMinutes = 50
                                        displayModel.breakMinutes = 10
                                        displayModel.longBreakMinutes = 20
                                    } else if (currentText === "short") {
                                        displayModel.studyMinutes = 15
                                        displayModel.breakMinutes = 5
                                        displayModel.longBreakMinutes = 15
                                    } else {
                                        // default: load from model's current or config
                                        // keep existing values
                                    }
                                }
                            }
                        }

                        // 学习分钟输入
                        SpinBox {
                            id: studySpin
                            from: 1; to: 180; stepSize: 1
                            value: displayModel ? displayModel.studyMinutes : 25
                            onValueChanged: { if (displayModel) displayModel.studyMinutes = value }
                            Layout.preferredWidth: 120
                        }

                        Text { text: "分"; verticalAlignment: Text.AlignVCenter }

                        // 休息分钟输入
                        SpinBox {
                            id: breakSpin
                            from: 5; to: 36; stepSize: 1
                            value: displayModel ? displayModel.breakMinutes : 5
                            onValueChanged: { if (displayModel) displayModel.breakMinutes = value }
                            Layout.preferredWidth: 120
                        }

                        Text { text: "休息分"; verticalAlignment: Text.AlignVCenter }

                        // 长休息分钟
                        SpinBox {
                            id: longSpin
                            from: 15; to: 30; stepSize: 1
                            value: displayModel ? displayModel.longBreakMinutes : 15
                            onValueChanged: { if (displayModel) displayModel.longBreakMinutes = value }
                            Layout.preferredWidth: 120
                        }

                        Text { text: "长休息分"; verticalAlignment: Text.AlignVCenter }

                        // cycles
                        SpinBox {
                            id: cyclesSpin
                            from: 1; to: 10; stepSize: 1
                            value: displayModel ? displayModel.cyclesBeforeLong : 4
                            onValueChanged: { if (displayModel) displayModel.cyclesBeforeLong = value }
                            Layout.preferredWidth: 90
                        }
                    }

                    // 人脸窗口（放大并居中）
                    Rectangle {
                        id: faceWindow
                        Layout.preferredWidth: parent.width
                        Layout.preferredHeight: 180
                        radius: 8
                        color: "#ffffff"
                        border.color: "#e6e6e6"
                        border.width: 1
                        Layout.alignment: Qt.AlignHCenter
                        Image {
                                id: faceImg
                                // Avoid using anchors on an item that may be affected by layout sizing.
                                // Use explicit sizing relative to the parent to prevent layout/anchor warnings.
                                width: parent.width
                                height: parent.height
                                source: displayModel ? displayModel.faceImage : ""
                                fillMode: Image.PreserveAspectCrop
                                cache: true
                            }
                    }

                    // 进度条
                    Rectangle {
                        Layout.preferredWidth: parent.width
                        height: 18
                        radius: 9
                        color: "#e6e6e6"
                        clip: true

                        Rectangle {
                            id: progressBar
                            x: 0
                            y: 0
                            height: parent.height
                            width: parent.width * ((displayModel ? displayModel.studyProgress : 0) / 100)
                            color: "#4caf50"
                            radius: 9
                        }
                    }

                    // 操作按钮（居中）
                    RowLayout {
                        Layout.alignment: Qt.AlignHCenter
                        spacing: 12

                        Button {
                            id: studyStartBtn
                            Layout.preferredWidth: 140
                            Layout.preferredHeight: 44
                            text: "开始"
                            background: Rectangle { color: "#165dff"; radius: 8 }
                            contentItem: Text { text: studyStartBtn.text; color: "white"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            onClicked: {
                                // 仅在尚未开始学习会话时请求摄像头权限
                                if (displayModel && displayModel.studySessionActive) {
                                    // 已在学习会话中，通知后端一次性提示
                                    root.studyStartAlreadyClicked()
                                } else {
                                    cameraDialog.open()
                                }
                            }
                        }

                        Button {
                            id: studyStopBtn
                            Layout.preferredWidth: 140
                            Layout.preferredHeight: 44
                            text: "停止/退出"
                            background: Rectangle { color: "#eceff3"; radius: 8 }
                            contentItem: Text { text: studyStopBtn.text; color: "#1d2129"; horizontalAlignment: Text.AlignHCenter; verticalAlignment: Text.AlignVCenter }
                            onClicked: {
                                root.studyStopClicked()
                                displayModel.studyModeActive = false
                            }
                        }
                    }
                }
            }

            // 摄像头权限确认对话框（放在布局外仍可定义于此处）
            Dialog {
                id: cameraDialog
                modal: true
                title: "摄像头权限"
                standardButtons: Dialog.Ok | Dialog.Cancel
                // Give the dialog an explicit implicitWidth to avoid binding loops
                implicitWidth: 440
                implicitHeight: 160
                onAccepted: {
                    // 用户允许，继续开始学习
                    root.studyStartClicked()
                }
                onRejected: {
                    // 用户拒绝，保持学习面板打开但不启动计时
                }
                contentItem: Item {
                    // Use anchors inside contentItem and margins, but avoid binding content width to parent.width
                    width: parent ? parent.width : 400
                    height: parent ? parent.height : 120
                    Text {
                        id: cameraText
                        anchors.fill: parent
                        anchors.margins: 20
                        text: "学习模式需要使用摄像头进行专注监控，是否允许？"
                        wrapMode: Text.WordWrap
                    }
                }
            }
        }
    }
}
