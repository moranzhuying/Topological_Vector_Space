# 拓扑向量空间

## 主要内容

Bourbaki《数学原本》(Éléments de mathématique) 中《拓扑向量空间》一卷的自学笔记。

## 说明

本笔记按 Bourbaki 原书的章节层级组织，对应关系如下：

| Bourbaki 原书 | 本笔记 | 本仓库中的示例 |
|---|---|---|
| 章（Chapitre） | `Content/` 下的**章目录** | `1_Topological_Vector_Spaces_over_a_Valued_Division_Ring/` |
| 节（§） | 章目录下的**节目录** | `1_Topological_vector_spaces/` |
| 小节（1、2、…） | 节目录下的 **`.tex` 文件** | `1_Definition_of_a_topological_vector_space.tex` |

- 目录与文件名取该层级标题的**英译**，并加编号前缀（`1_`、`2_`…，不加前导零）。
- 中文标题写在 `\chapter{...}` 与 `\section{...}` 中：`\chapter{}` 用该**节目录**名的中译，`\section{}` 用该**文件**名的中译。
- 每层目录各有一个 `index.tex`，按顺序汇总对下一层的 `\input`。

定理环境用法、交叉引用（`\cref`）、符号库维护等 **tex 层面的规定**，另见模板《笔记写作》的 README。

## 内容结构

```
Content/
├─ 1_Topological_Vector_Spaces_over_a_Valued_Division_Ring/
│  ├─ 1_Topological_vector_spaces/
│  ├─ 2_Linear_varieties_in_a_topological_vector_space/
│  └─ 3_Metrisable_topological_vector_spaces/
├─ 2_Convex_Sets_and_Locally_Convex_Spaces/
│  ├─ 1_Semi-norms/
│  ├─ 2_Convex_sets/
│  ├─ 3_The_Hahn-Banach_Theorem_(analytic_form)/
│  ├─ 4_Locally_convex_spaces/
│  ├─ 5_Separation_of_convex_sets/
│  ├─ 6_Weak_topologies/
│  ├─ 7_Extremal_points_and_extremal_generators/
│  └─ 8_Complex_locally_convex_spaces/
├─ 3_Spaces_of_Continous_Linear_Mappings/
│  ├─ 1_Bornology_in_a_topological_vector_space/
│  ├─ 2_Bornological_spaces/
│  ├─ 3_Spaces_of_continuous_linear_mappings/
│  ├─ 4_The_Banach-Steinhaus_theorem/
│  ├─ 5_Hypocontinuous_bilinear_mappings/
│  └─ 6_Borel's_graph_theorem/
├─ 4_Duality_in_Topological_Vector_Spaces/
│  ├─ 1_Duality/
│  ├─ 2_Bidual_Reflexive_spaces/
│  ├─ 3_Dual_of_a_Fréchet_space/
│  ├─ 4_Strict_morphisms_of_Fréchet_spaces/
│  ├─ 5_Compactness_criteria/
│  └─ Appendix_Fixed_points_of_groups_of_affine_transformations/
├─ 5_Hillbertian_Spaces_Elementary_Theory/
│  ├─ 1_Prehilbertian_spaces_and_hilbertian_spaces/
│  ├─ 2_Orthogonal_families_in_a_hilbertian_space/
│  ├─ 3_Tensor_product_of_hilbertian_spaces/
│  └─ 4_Some_classes_of_operators_in_hilbertian_spaces/
├─ 6_Topological_Tensor_Products/
│  ├─ 1_Complements_on_semi-normed_spaces/
│  ├─ 2_Topological_tensor_products/
│  ├─ 3_Examples_of_topological_tensor_products/
│  ├─ 4_Dualities_and_envelopes_of_tensor_constructions/
│  └─ 5_Grothendieck's_inequality/
└─ 7_Nuclear_Mappings_and_Spaces/
   ├─ 1_Nuclear_mappings/
   ├─ 2_Trace_and_determinant_in_Hilbertian_spaces/
   ├─ 3_Trace_and_determinant_in_Banach_spaces/
   └─ 4_Nuclear_spaces/
```

## 文件结构

```
main.tex          编译入口
structure.sty     样式包：页面设置、定理环境、引用、数学符号库
quiver.sty        交换图支持
Content/          分章正文，每章一个目录，由 index.tex 汇总 \input
commit.py         一键提交并推送（说明见 commit.md）
setup_mode.py     习题编排模式切换（说明见 setup_mode.md）
README.md         本文件：项目说明
CHANGELOG.md      更新日志：tex 配置调整与正文内容调整
```

各脚本的选项与功能分别见 [commit.md](commit.md) 与 [setup_mode.md](setup_mode.md)；符号库由上层目录的 `symbols.py` 统一管理。

## 编译

本笔记使用自建的【笔记写作】模板（样式包 `structure.sty`），须用 **XeLaTeX** 编译：

```bash
xelatex main.tex
```

- **编译环境**：XeLaTeX。模板依赖 ctexbook 与 XeLaTeX 特性，**不支持 pdfLaTeX**。
- **TeXStudio**：建议 4.0 或更高版本。
- `main.pdf` 未纳入版本控制，需本地编译生成。
