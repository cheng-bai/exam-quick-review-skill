# 改编示例：从候选题到可教学题族

以下完整数学例题为技能维护者据来源主题补写、核算的示范，不是视频原题的逐字还原。只读取与当前任务相关的例子，不固定用户的题数、难度或表述。

## 一、和等于积：同一关系，任务与方法可以变化

### 母题

求满足 $a+b=ab$ 的所有正整数有序对 $(a,b)$。

**答案与机制。** $(a-1)(b-1)=1$，所以只有 $(2,2)$。核心是将和积关系变为移位因子的乘积，再利用数域限制。

### 对象与表示

**题目。** 求所有满足 $x+y=xy$ 的实数点，并求其中整数点。

**答案。** 曲线 $(x-1)(y-1)=1$；$x\ne1$ 时 $y=1+1/(x-1)$；整数点为 $(2,2),(0,0)$。若仍限定正整数，只能取前一个点。

**新增动作。** 关联连续曲线与整数格点；区分数域，不把全部实数解用整数因子枚举。

### 代换与合法逆像

**题目。** $x,y>1$，$\ln x,\ln y$ 为正整数，且 $\ln x+\ln y=(\ln x)(\ln y)$，求 $(x,y)$。

**答案。** 令 $a=\ln x,b=\ln y$，得 $(x,y)=(e^2,e^2)$，满足全部条件。

**新增动作。** 识别中间对象，回代并检查范围。不能仅换成复杂表达式而忽略逆像。

### 增加个数，允许方法换入口

**题目。** 求全部满足 $a+b+c=abc$ 的正整数有序三元组。

**答案。** $(1,2,3)$ 的六个排列。先设 $a\le b\le c$，由 $abc=a+b+c\le3c$ 得 $ab\le3$。只需 $(a,b)=(1,1),(1,2),(1,3)$，分别无解、$c=3$、$c=2$ 不合排序。

**新增动作。** 对称排序与估计。它保留研究关系，但不强制沿用两元因式分解。

### 一般个数，先选适当任务

**题目。** 对每个整数 $n\ge2$，是否存在 $n$ 个正整数的和等于积？给出一种构造。

**答案。** 取 $n-2$ 个 $1$，再取 $2,n$，和与积均为 $2n$。

**用途。** 训练一般构造。只证明存在，未分类全部解，不能冒充全部解题。

### 隐藏系数的一般化

**题目。** 给定正整数 $k$，求所有满足 $ab=k(a+b)$ 的正整数有序对。

**答案。** $(a-k)(b-k)=k^2$；由 $k/a+k/b=1$ 得 $a,b>k$。对每个正因子 $d\mid k^2$，全部解为

$$
(a,b)=\left(k+d,k+\frac{k^2}{d}\right).
$$

**新增动作。** 参数与因子结构。明确 $k$ 为正整数，不能将这套整除描述照搬到任意实数参数。

## 二、空间向量：符号、取等和等价翻译

### 母题与共同证据

空间单位向量 $\mathbf a,\mathbf b,\mathbf c$ 满足 $\mathbf a\perp\mathbf b$、$\mathbf a\perp\mathbf c$，$\angle(\mathbf b,\mathbf c)=60^\circ$。单位向量 $\mathbf p$ 满足

$$
|\mathbf p\cdot\mathbf c|\le|\mathbf p\cdot\mathbf b|\le|\mathbf p\cdot\mathbf a|.
$$

求 $\mathbf p\cdot\mathbf c$ 的最大值。

记 $u=\mathbf p\cdot\mathbf a,v=\mathbf p\cdot\mathbf b,w=\mathbf p\cdot\mathbf c$。非正交投影满足

$$
1=u^2+\frac43(v^2-vw+w^2).
$$

考虑 $w>0$，设 $t=v/w$，则 $|t|\ge1$、$u^2\ge v^2$，从而

$$
1\ge\frac{7t^2-4t+4}{3}w^2\ge\frac73w^2.
$$

二次式在 $|t|\ge1$ 上于 $t=1$ 最小。最大值为 $m=\sqrt{3/7}$。取

$$
\mathbf p=\pm m\mathbf a+\frac{2m}{3}(\mathbf b+\mathbf c)
$$

满足单位长度与全部比较条件，达到 $w=m$。不能把 $u^2+v^2+w^2$ 当单位长度。

### 一般化：锐角与钝角必须分支

**题目。** 空间单位向量 $\mathbf a,\mathbf b,\mathbf c$ 满足 $\mathbf a\perp\mathbf b$、$\mathbf a\perp\mathbf c$，夹角 $\theta=\angle(\mathbf b,\mathbf c)\in(0,\pi)$。单位向量 $\mathbf p$ 满足 $|\mathbf p\cdot\mathbf c|\le|\mathbf p\cdot\mathbf b|\le|\mathbf p\cdot\mathbf a|$。求 $\mathbf p\cdot\mathbf c$ 的最大值。

**解析。** 令 $r=\cos\theta$，有

$$
1=u^2+\frac{v^2-2rvw+w^2}{1-r^2}
\ge w^2\left[t^2+\frac{t^2-2rt+1}{1-r^2}\right],\quad |t|\ge1.
$$

二次式顶点 $r/(2-r^2)$ 在 $(-1,1)$。比较 $t=1,-1$，得

$$
M(\theta)=\sqrt{\frac{1+|\cos\theta|}{3+|\cos\theta|}}.
$$

**取等。** 令 $w=M,|u|=M$；锐角取 $v=M$，钝角取 $v=-M$，直角任一符号。取正交基 $\mathbf b,\mathbf d,\mathbf a$，其中 $\mathbf d=(\mathbf c-r\mathbf b)/\sqrt{1-r^2}$，可明确构造

$$
\mathbf p=v\mathbf b+\frac{M-rv}{\sqrt{1-r^2}}\mathbf d+u\mathbf a.
$$

代入恰有长度 $1$、目标投影 $M$，所以最大值可达到。

**通过标准。** 必须解释绝对值与投影符号。只换另一个锐角套公式属于熟练度练习；扩展钝角增加了新的边界。

### 反向：同一最大值可能有两个夹角

**题目。** 在空间中，单位向量 $\mathbf a$ 垂直单位向量 $\mathbf b,\mathbf c$，它们夹角为 $\theta\in(0,\pi)$。单位 $\mathbf p$ 满足 $|\mathbf p\cdot\mathbf c|\le|\mathbf p\cdot\mathbf b|\le|\mathbf p\cdot\mathbf a|$。若目标 $\mathbf p\cdot\mathbf c$ 的最大值为 $\sqrt{3/7}$，求全部夹角 $\theta$。

**答案。** $|\cos\theta|=1/2$，所以 $\theta=\pi/3$ 或 $2\pi/3$。取值范围为 $1/\sqrt3\le M<1/\sqrt2$，右端不达到，因为 $0,\pi$ 被排除。

**用途。** 检查反求时的两支及参数域，不只找回母题的 $60^\circ$。

### 图形：完整保留绝对值的距离题

**题目。** $OA=OB=OC=1$，$OA\perp OB$、$OA\perp OC$，$\angle BOC=60^\circ$。$A^-,B^-,C^-$ 分别为 $A,B,C$ 关于 $O$ 的对称点。点 $P$ 在单位球面上，满足

$$
\min(PA,PA^-)\le\min(PB,PB^-)\le\min(PC,PC^-).
$$

求 $PC$ 的最小值。

**答案与解析。** 最近距离的平方分别为 $2-2|u|,2-2|v|,2-2|w|$，故条件精确对应母题；$PC^2=2-2w$，得到

$$
PC_{\min}=\sqrt{2-2\sqrt{3/7}}.
$$

取母题的取等点即可。

**易错边界。** 仅写 $PA\le PB\le PC$ 对应有符号投影的比较，已经改变原约束。它可单独成为另一道新题，但不能宣称是母题的等价翻译。
