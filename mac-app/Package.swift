// swift-tools-version:5.9
import PackageDescription

let package = Package(
    name: "CloudMountBar",
    platforms: [.macOS(.v14)],
    targets: [
        .executableTarget(
            name: "CloudMountBar",
            path: "Sources/CloudMountBar"
        )
    ]
)
