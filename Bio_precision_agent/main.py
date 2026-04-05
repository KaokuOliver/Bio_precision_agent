import os
import sys
import json
from dotenv import load_dotenv
from core.agents import BioPrecisionAgents

# 强制重构 Windows 环境下的标准输出编码为 utf-8，避免打印 Emoji 报错
sys.stdout.reconfigure(encoding='utf-8')

# 加载当前目录的 .env 文件（如果在本地测试则需要它）
load_dotenv()

def main():
    print("🔬 正在初始化 Bio-Precision Agent CLI 测试工作流 (DeepSeek 版)...")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        print("❌ [错误] 启动拦截：系统未检测到 `DEEPSEEK_API_KEY`")
        print("请在本目录创建一个名为 `.env` 的文件，填入 `DEEPSEEK_API_KEY=sk-...` 开头的密钥。")
        return

    # 初始化 DeepSeek 客户端
    agent_system = BioPrecisionAgents(api_key=api_key, model_name="deepseek-chat")
    
    # 根据需求要求，测试“麻竹差异表达分析”案例
    user_input = "我想做麻竹的 DREB 基因家族差异表达分析，需要确切的步骤和代码库建议"
    
    print("=" * 60)
    print(f"📌 初始粗糙意图: {user_input}\n")

    print("⏳ [Step 1] Architect 领域建模与参数解析中...")
    architect_data = agent_system.run_architect(user_input)
    print(f"✔️ 结构化提取结果:\n{json.dumps(architect_data, indent=2, ensure_ascii=False)}\n")

    print("-" * 60)
    print("⏳ [Step 2] Researcher 互联网真实证据溯源检索中...")
    researcher_result = agent_system.run_researcher(user_input, architect_data)
    synthesis = researcher_result["synthesis"]
    chunks = researcher_result["chunks"]
    print(f"✔️ 证据片段数量: {len(chunks)}")
    print(f"✔️ 证据综合分析 (截取前800字): \n\n{synthesis[:800]}...\n")

    print("-" * 60)
    print("⏳ [Step 3] Validator 三方交叉验证，无信源标记中...")
    report = agent_system.run_validator(user_input, architect_data, researcher_result)
    
    print("\n✔️ 【无幻觉执行级报告 (终端展示部分)】")
    print("=" * 60)
    print(report[:800] + "\n...\n(终端仅显示前 800 字)")
    print("=" * 60)

    # 导出文件
    out_file = "bpa_test_report.md"
    with open(out_file, "w", encoding="utf-8") as f:
         f.write(report)
    print(f"\n[+] 验证流程成功！完整报告已导出至同级目录 => {out_file}")

if __name__ == "__main__":
    main()
