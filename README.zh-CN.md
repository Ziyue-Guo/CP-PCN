# CP-PCN：作物群体点云补全网络

**从可见表面点云补全被遮挡的作物冠层结构。**

[English](README.md) | [简体中文](README.zh-CN.md) · [论文](https://doi.org/10.1016/j.xplc.2025.101675) · [数据说明](docs/DATA.md) · [运行指南](docs/USAGE.md)

本仓库为论文 **A novel point cloud completion model for three-dimensional reconstruction of complex, dynamic population-level crop canopy architecture** 的配套研究代码。正式引文为 Guo 等，*Plant Communications* **7**(3)，101675，**2026** 年。

研究流程以单株三维重建、群体模拟和可见性划分构造训练数据，通过多分辨率动态图编码器和点金字塔解码器预测遮挡点。编码器在各尺度提取动态图特征，判别器也采用动态图操作进行对抗训练。已有可见点与预测遮挡点共同构成补全结果。

![CP-PCN 研究流程与模型概览](docs/assets/cp-pcn-overview.svg)

## 仓库现状

| 内容 | 当前状态 |
| --- | --- |
| 模型、训练、推理及历史分析脚本 | 已包含 |
| 示例数据 | 输入和目标目录各 80 个 XYZ `.pts` 文件，另有 CSV/TXT 示例 |
| 数据划分 | train 72、val 16、test 8；**16 个 val ID 全部也在 train 中** |
| 预训练权重 | 当前 Git 文件树及 Releases 未提供 |
| 论文完整数据集和环境锁定文件 | 仓库未提供 |
| 独立数据检查工具、自动检查 | 2026 年 10 月新增 |

本次维护保留原模型代码、点云、划分清单和 MIT 许可证，补齐文档、引用与只读数据检查工具，**不代表已经能够直接训练或已经复现论文结果**。

旧文件中的 `RP_PCN` / `RPPCN` 命名保留以兼容现有代码；论文模型名称为 **CP-PCN**。

## 论文报告的表现

以下引用论文模型比较部分，**不是本次重新运行结果**：

| 油菜生育期 | 论文报告的 Chamfer distance |
| --- | ---: |
| 苗期 | 3.35 cm |
| 薹期 | 3.46 cm |
| 花期 | 4.32 cm |
| 角果期 | 4.51 cm |

源码损失包含平方距离和缩放，不能直接将其原始数值视为表中的厘米值，详见[复现说明](docs/REPRODUCIBILITY.md)。

水稻实验是在水稻数据上**从头重新训练模型**，不能表述为油菜权重直接零样本迁移到水稻。

## 快速开始：不需要 GPU 的数据检查

新增工具仅依赖 **Python 3.11+ 标准库**：

```bash
git clone https://github.com/Ziyue-Guo/CP-PCN.git
cd CP-PCN
python tools/check_dataset.py --cloud dataset/mydata/02691156/points/moved_IMG_4580_frames_down.pts
```

检查整个成对数据集和三份划分文件：

```bash
python tools/check_dataset.py --root dataset/mydata
```

**随附数据的预期结果：** 全量检查因 train/val 共享 16 个 ID 而返回非零状态。维护没有重写历史划分；单文件格式通过不能证明评估集独立。

工具不下采样、不归一化、不覆盖原始点云。格式及准备方法见[数据说明](docs/DATA.md)。

## 训练、预测与分析

先阅读[运行指南](docs/USAGE.md)，准备依赖、路径、CUDA 环境和预测所需权重。

| 任务 | 实际入口 |
| --- | --- |
| 训练 | `Train_RP_PCN.py` |
| CSV 示例预测 | `Test_csv.py` |
| 历史距离分析 | `show_CD.py` |
| 历史补全导出 | `show_recon_RPPCN.py` |
| 群体和遮挡数据生成 | `create_dataset.py` |
| 历史 COLMAP 批处理 | `COLMAP_batch.py` |

距离分析和补全导出脚本还需与当前 loader、点数配置对齐。仓库没有 `evaluate.py`、`visualize_results.py`，此前 README 中的 `Train_RPPCN.py` 拼写及 `requirements.txt` 安装入口已更正。

- [数据说明](docs/DATA.md)：80 对示例、点云格式、划分重叠及权重状态。
- [运行指南](docs/USAGE.md)：依赖、实际参数、路径与旧脚本限制。
- [复现说明](docs/REPRODUCIBILITY.md)：论文证据、指标单位、已知实现差异和维护边界。
- [贡献指南](CONTRIBUTING.md)：反馈和后续验证约定。

## 引用

Guo, Z., Yang, X., Shen, Y., Zhu, Y., Jiang, L., & Cen, H. (2026). A novel point cloud completion model for three-dimensional reconstruction of complex, dynamic population-level crop canopy architecture. *Plant Communications*, 7(3), 101675. https://doi.org/10.1016/j.xplc.2025.101675

可使用 [BibTeX](references.bib) 或 GitHub 的 **Cite this repository**。DOI 中保留 `2025`，但正式卷期引文年份为 **2026**，不再沿用旧的 in-press 信息。

## 致谢、许可与反馈

本工作基于 [PF-Net（CVPR 2020）](https://github.com/zztianzz/PF-Net-Point-Fractal-Network) 扩展。复用相关组件时请保留上游归属信息。仓库原有 [MIT 许可证](LICENSE)保持不变。

问题和资源请求可通过 [Issues](https://github.com/Ziyue-Guo/CP-PCN/issues) 提交，请附环境、命令和完整报错。
