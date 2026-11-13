# Codex App / CLI 共用 Server

一套可安装的 **Codex skill**，附可选的 **Linux C++ 启动适配器**：让 App 与
CLI 使用同一现有本地 backend，定位真实故障并保留在途工作。

[English](README.md)

## 内容

- skill：判断实际 backend 和会话归属，区分连接、工具目录、实际调用与任务接续。
- 机制与验证参考：动态 pipe、有效配置、版本边界、选择性回滚。
- C++17 源码、CMake 和显式启动 wrapper，复用已安装的 App 与 daemon。

这是社区集成方案。包内没有 App、厂商插件源码、登录凭据或私人研究数据。

## 安装与使用

用 Codex 的 skill installer 安装本仓库的 **`codex-shared-server/` 目录**，或将该
目录复制到你配置的 skills root。安装 skill 本身不修改 App、daemon 或权限。

在 Codex 中说：

> 用 $codex-shared-server 确认我的 App 和 CLI 是否共用 backend，修复实际的连接问题，保留正在进行的工作。

适用场景：CLI 报 notLoaded 但 App 正在工作；App 重启后工具消失；需要验证原会话
恢复，或只回滚本次改动的配置项。

工作流先只读定位。如需使用 Linux 适配器，按[配置说明](codex-shared-server/references/linux-binding.md)
填入实际已安装路径。它不会获取凭据、创建 daemon、自动关闭 App 或增加后台服务。
对在途任务有影响的重启，应沿现有 owner 和授权协调。

## 证据与范围

原实现完成了真实隔离 App 重启、同 daemon 原/新调用者、选择性回滚，以及正式环境
普通工具与原会话接续验证。公开适配器的包级测试另列范围，见[验证说明](codex-shared-server/references/verification.md)。

原观察版本为 Linux App **26.1007.71326**、bundled CLI **0.162.0-alpha.17.2**、
官方 daemon **0.167.0**。这是一组历史验证版本，不宣称所有版本和平台兼容。

特定 `openai/userVerification` 仍仅支持 stdio；全部带签名的 workspace/browser
流程、内部菜单 relaunch、多个 App profile 并未全部验证。普通调用成功不等于所有
功能通过，方案保留厂商身份及权限检查。

## 复现协议测试

公开包包含 21 项合成 fixture，用于检查配置保留、选择性回滚、所有权、回读失配和
结果不确定的写入。测试不会启动真实 Codex 或模型，与真实隔离 App 的证据分开。
构建 helper 后，按[测试说明](tests/README.md)运行；Python 测试依赖 `websockets`。
预期内的边界观察单独标注，不混作真实功能通过。

## 隐私和许可证

只公开通用流程与自己编写的 helper 源码。实际配置、主机路径、凭据、会话/Goal、
截图、日志和实时 socket 标识均留在本机。你自己的诊断及回滚快照也应私有保存。
helper 使用现有 owner-only Unix socket，不增加公开监听、代理或持久服务。

采用 MIT 许可证；Boost/jsoncpp 及 Codex 软件各自保留原许可证，包内不分发其源码或
二进制。文件布局见英文 README。
