ComboBox {
    id: presetModeCombo
    text: "预设模式"
    model: [
        "default",
        "deep",
        "short"
    ]
    delegate: ItemDelegate {
        text: modelData
        font.pixelSize: 24
        letterSpacing: 1
        anchors.centerIn: parent
    }
}
