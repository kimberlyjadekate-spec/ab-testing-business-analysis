import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

from scipy.stats import chisquare
from statsmodels.stats.proportion import proportions_ztest
from statsmodels.stats.power import NormalIndPower
from statsmodels.stats.proportion import proportion_effectsize

# 读取 A/B Test 数据
df = pd.read_excel("data/ab_data.xlsx")

# 查看前 5 行
print(df.head())

# 查看数据规模
print(df.shape)

# 1. 检查缺失值
print("\nMissing values:")
print(df.isnull().sum())

# 2. 检查用户是否重复出现
print("\nUnique users:")
print(df["user_id"].nunique())

print("\nTotal rows:")
print(len(df))

print("\nDuplicated user records:")
print(df["user_id"].duplicated().sum())

# 3. 检查实验分组与实际页面是否一致
mismatch = df[
    ((df["group"] == "control") & (df["landing_page"] != "old_page")) |
    ((df["group"] == "treatment") & (df["landing_page"] != "new_page"))
]

print("\nMismatched assignments:")
print(len(mismatch))

print("\nExamples of mismatched records:")
print(mismatch.head())

print("\nTotal mismatched assignments:", len(mismatch))

# 4. 清除实验分组与实际页面不一致的记录
df_clean = df.drop(mismatch.index).copy()

print("\nRows after removing mismatched assignments:")
print(len(df_clean))

# 5. 检查清洗后是否仍存在重复用户
duplicate_users = df_clean[
    df_clean["user_id"].duplicated(keep=False)
]

print("\nRemaining duplicated users:")
print(duplicate_users)

# 6. 每个用户只保留第一次实验记录
df_clean = (
    df_clean
    .sort_values("timestamp")
    .drop_duplicates(subset="user_id", keep="first")
    .copy()
)

print("\nFinal cleaned rows:")
print(len(df_clean))

print("\nFinal unique users:")
print(df_clean["user_id"].nunique())

print("\nRemaining duplicated users:")
print(df_clean["user_id"].duplicated().sum())

# 7. 检查 A/B 两组样本量
group_counts = df_clean["group"].value_counts()

print("\nGroup sample sizes:")
print(group_counts)

print("\nGroup proportions:")
print(df_clean["group"].value_counts(normalize=True))

# 8. SRM 检验：检查实验流量是否符合预期的 50/50 分配
observed = [
    group_counts["control"],
    group_counts["treatment"]
]

expected = [
    len(df_clean) / 2,
    len(df_clean) / 2
]

chi2_stat, srm_p_value = chisquare(
    f_obs=observed,
    f_exp=expected
)

print("\nSRM Test:")
print("Observed:", observed)
print("Expected:", expected)
print("Chi-square statistic:", chi2_stat)
print("SRM p-value:", srm_p_value)

# 9. 计算 Control 和 Treatment 的转化率
conversion_summary = df_clean.groupby("group")["converted"].agg(
    users="count",
    conversions="sum",
    conversion_rate="mean"
)

print("\nConversion Summary:")
print(conversion_summary)

control_rate = conversion_summary.loc["control", "conversion_rate"]
treatment_rate = conversion_summary.loc["treatment", "conversion_rate"]

absolute_uplift = treatment_rate - control_rate
relative_uplift = absolute_uplift / control_rate

print("\nControl conversion rate:", f"{control_rate:.4%}")
print("Treatment conversion rate:", f"{treatment_rate:.4%}")
print("Absolute uplift:", f"{absolute_uplift:.4%}")
print("Relative uplift:", f"{relative_uplift:.2%}")

# 10. Two-Proportion Z-Test
count = [
    conversion_summary.loc["treatment", "conversions"],
    conversion_summary.loc["control", "conversions"]
]

nobs = [
    conversion_summary.loc["treatment", "users"],
    conversion_summary.loc["control", "users"]
]

z_stat, p_value = proportions_ztest(
    count=count,
    nobs=nobs,
    alternative="two-sided"
)

print("\nTwo-Proportion Z-Test:")
print("Z-statistic:", z_stat)
print("p-value:", p_value)

# 11. 计算转化率差异的 95% Confidence Interval
import numpy as np

control_n = conversion_summary.loc["control", "users"]
treatment_n = conversion_summary.loc["treatment", "users"]

se_diff = np.sqrt(
    treatment_rate * (1 - treatment_rate) / treatment_n
    + control_rate * (1 - control_rate) / control_n
)

ci_lower = absolute_uplift - 1.96 * se_diff
ci_upper = absolute_uplift + 1.96 * se_diff

print("\n95% Confidence Interval:")
print("Lower bound:", f"{ci_lower:.4%}")
print("Upper bound:", f"{ci_upper:.4%}")

# 12. Power Analysis / Minimum Detectable Effect (MDE)

power_analysis = NormalIndPower()

n_control = conversion_summary.loc["control", "users"]
n_treatment = conversion_summary.loc["treatment", "users"]

# 两组样本量比例
ratio = n_treatment / n_control

# 在 alpha=0.05、power=0.80 下计算最小可检测 effect size
mde_effect_size = power_analysis.solve_power(
    effect_size=None,
    nobs1=n_control,
    alpha=0.05,
    power=0.80,
    ratio=ratio,
    alternative="two-sided"
)

print("\nPower Analysis:")
print("Minimum detectable standardized effect size:", mde_effect_size)

# 将 standardized effect size 转换成实际转化率 MDE
baseline_rate = control_rate

# Cohen's h = 2*asin(sqrt(p1)) - 2*asin(sqrt(p2))
baseline_angle = 2 * np.arcsin(np.sqrt(baseline_rate))

mde_upper_rate = np.sin(
    (baseline_angle + mde_effect_size) / 2
) ** 2

mde_absolute = mde_upper_rate - baseline_rate
mde_relative = mde_absolute / baseline_rate

print("\nBusiness MDE:")
print("Baseline conversion rate:", f"{baseline_rate:.4%}")
print("Minimum detectable absolute change:", f"{mde_absolute:.4%}")
print("Minimum detectable relative change:", f"{mde_relative:.2%}")

# 13. 检查实验运行时间
df_clean["timestamp"] = pd.to_datetime(df_clean["timestamp"])

experiment_start = df_clean["timestamp"].min()
experiment_end = df_clean["timestamp"].max()
experiment_duration = experiment_end - experiment_start

print("\nExperiment Period:")
print("Start:", experiment_start)
print("End:", experiment_end)
print("Duration:", experiment_duration)

# 14. 检查每日实验流量和转化率稳定性
df_clean["date"] = df_clean["timestamp"].dt.date

daily_summary = df_clean.groupby(["date", "group"]).agg(
    users=("user_id", "count"),
    conversion_rate=("converted", "mean")
).reset_index()

print("\nDaily Experiment Summary:")
print(daily_summary)

# 每日总流量
daily_traffic = df_clean.groupby("date")["user_id"].count()

print("\nDaily Total Traffic:")
print(daily_traffic)

print("\nDaily Traffic Statistics:")
print(daily_traffic.describe())

# 15. Visualize daily traffic stability

daily_traffic = df_clean.groupby("date")["user_id"].count()

plt.figure(figsize=(12, 5))

plt.plot(
    daily_traffic.index,
    daily_traffic.values,
    marker="o"
)

plt.axhline(
    daily_traffic.mean(),
    linestyle="--",
    label=f"Average = {daily_traffic.mean():.0f}"
)

plt.title("Daily Experiment Traffic")
plt.xlabel("Date")
plt.ylabel("Number of Users")
plt.xticks(rotation=45)
plt.legend()
plt.tight_layout()

plt.show()

# 16. Daily conversion rate by experiment group

daily_conversion = (
    df_clean
    .groupby(["date", "group"])["converted"]
    .mean()
    .unstack()
)

plt.figure(figsize=(12, 5))

plt.plot(
    daily_conversion.index,
    daily_conversion["control"],
    marker="o",
    label="Control"
)

plt.plot(
    daily_conversion.index,
    daily_conversion["treatment"],
    marker="o",
    label="Treatment"
)

plt.title("Daily Conversion Rate: Control vs Treatment")
plt.xlabel("Date")
plt.ylabel("Conversion Rate")

plt.gca().yaxis.set_major_formatter(
    plt.FuncFormatter(lambda y, _: f"{y:.1%}")
)

plt.xticks(rotation=45)
plt.legend()
plt.tight_layout()

plt.show()

# 17. Load country data

countries = pd.read_excel("data/countries.xlsx")

print("\nCountry Data:")
print(countries.head())

print("\nCountry Data Shape:")
print(countries.shape)

print("\nCountry Columns:")
print(countries.columns)

print("\nMissing Values:")
print(countries.isnull().sum())

print("\nCountry Distribution:")
print(countries["country"].value_counts())

# 18. Validate country data before merging

print("\nCountry unique users:")
print(countries["user_id"].nunique())

print("\nCountry total rows:")
print(len(countries))

print("\nDuplicated user IDs in country data:")
print(countries["user_id"].duplicated().sum())

# Check whether all experiment users have country information
missing_country_users = (
    set(df_clean["user_id"]) - set(countries["user_id"])
)

print("\nExperiment users without country data:")
print(len(missing_country_users))

# 19. Merge experiment data with country information

df_analysis = df_clean.merge(
    countries,
    on="user_id",
    how="left",
    validate="one_to_one"
)

print("\nMerged Data Shape:")
print(df_analysis.shape)

print("\nMissing country after merge:")
print(df_analysis["country"].isnull().sum())

print("\nMerged Data Preview:")
print(df_analysis.head())

# 20. Country-level A/B test performance

country_summary = (
    df_analysis
    .groupby(["country", "group"])["converted"]
    .agg(
        users="count",
        conversions="sum",
        conversion_rate="mean"
    )
    .reset_index()
)

print("\nCountry-level A/B Performance:")
print(country_summary)

# 21. Country-level statistical tests

country_results = []

for country in df_analysis["country"].unique():

    subset = df_analysis[df_analysis["country"] == country]

    control = subset[subset["group"] == "control"]
    treatment = subset[subset["group"] == "treatment"]

    n_control = len(control)
    n_treatment = len(treatment)

    conv_control = control["converted"].sum()
    conv_treatment = treatment["converted"].sum()

    rate_control = control["converted"].mean()
    rate_treatment = treatment["converted"].mean()

    # Treatment - Control
    diff = rate_treatment - rate_control
    relative_uplift = diff / rate_control

    # Two-proportion z-test
    count = np.array([conv_treatment, conv_control])
    nobs = np.array([n_treatment, n_control])

    z_stat, p_value = proportions_ztest(
        count,
        nobs,
        alternative="two-sided"
    )

    # 95% CI for difference in proportions
    se = np.sqrt(
        rate_treatment * (1 - rate_treatment) / n_treatment +
        rate_control * (1 - rate_control) / n_control
    )

    ci_lower = diff - 1.96 * se
    ci_upper = diff + 1.96 * se

    country_results.append({
        "country": country,
        "control_rate": rate_control,
        "treatment_rate": rate_treatment,
        "absolute_uplift": diff,
        "relative_uplift": relative_uplift,
        "p_value": p_value,
        "ci_lower": ci_lower,
        "ci_upper": ci_upper
    })

country_results = pd.DataFrame(country_results)

print("\nCountry-level Statistical Results:")
print(country_results.to_string(index=False))

# =========================================================
# 22. Business Decision
# =========================================================

alpha = 0.05

# Recalculate overall A/B test metrics
control_data = df_clean[df_clean["group"] == "control"]
treatment_data = df_clean[df_clean["group"] == "treatment"]

control_users = len(control_data)
treatment_users = len(treatment_data)

control_conversions = control_data["converted"].sum()
treatment_conversions = treatment_data["converted"].sum()

overall_control_rate = control_conversions / control_users
overall_treatment_rate = treatment_conversions / treatment_users

overall_absolute_uplift = overall_treatment_rate - overall_control_rate
overall_relative_uplift = overall_absolute_uplift / overall_control_rate

# Two-proportion Z-test
count = np.array([treatment_conversions, control_conversions])
nobs = np.array([treatment_users, control_users])

overall_z_stat, overall_p_value = proportions_ztest(count, nobs)

# 95% confidence interval for treatment - control
se = np.sqrt(
    overall_treatment_rate * (1 - overall_treatment_rate) / treatment_users
    + overall_control_rate * (1 - overall_control_rate) / control_users
)

overall_ci_lower = overall_absolute_uplift - 1.96 * se
overall_ci_upper = overall_absolute_uplift + 1.96 * se

# Print business summary
print("\n" + "=" * 55)
print("A/B TEST BUSINESS DECISION")
print("=" * 55)

print(f"Control conversion rate:   {overall_control_rate:.4%}")
print(f"Treatment conversion rate: {overall_treatment_rate:.4%}")
print(f"Absolute uplift:           {overall_absolute_uplift:.4%}")
print(f"Relative uplift:           {overall_relative_uplift:.2%}")
print(f"P-value:                   {overall_p_value:.4f}")
print(
    f"95% CI:                    "
    f"[{overall_ci_lower:.4%}, {overall_ci_upper:.4%}]"
)

if overall_p_value < alpha and overall_absolute_uplift > 0:
    decision = "SHIP"
    explanation = "The new page significantly improves conversion."

elif overall_p_value < alpha and overall_absolute_uplift < 0:
    decision = "DO NOT SHIP"
    explanation = "The new page significantly reduces conversion."

else:
    decision = "DO NOT SHIP"
    explanation = (
        "There is insufficient statistical evidence that the new page "
        "improves conversion."
    )

print("\nDecision:", decision)
print("Reason:", explanation)

print("=" * 55)

# =========================================================
# 23. Visualize Overall Treatment Effect with 95% CI
# =========================================================

import matplotlib.pyplot as plt

# Convert effect sizes to percentage points
effect_pp = overall_absolute_uplift * 100
ci_lower_pp = overall_ci_lower * 100
ci_upper_pp = overall_ci_upper * 100

# Calculate asymmetric error bars
lower_error = effect_pp - ci_lower_pp
upper_error = ci_upper_pp - effect_pp

plt.figure(figsize=(8, 5))

plt.errorbar(
    x=effect_pp,
    y=0,
    xerr=[[lower_error], [upper_error]],
    fmt="o",
    capsize=8,
    markersize=8
)

# Zero-effect reference line
plt.axvline(
    x=0,
    linestyle="--",
    linewidth=1.5
)

plt.yticks([0], ["New Page vs Old Page"])

plt.xlabel("Change in Conversion Rate (percentage points)")
plt.title("Overall Treatment Effect with 95% Confidence Interval")

plt.grid(axis="x", alpha=0.3)
plt.tight_layout()

plt.show()