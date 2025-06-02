#!/usr/bin/env python3
"""
マークダウン変換機能のテストスクリプト
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.handlers.pdf_summary import PDFSummaryHandler

def test_markdown_conversion():
    """マークダウン変換のテスト"""
    
    # テスト用のマークダウンテキスト
    test_markdown = """
## 第X回ゼミ議事録：舛田岳氏発表（202X年5月28日）

### 1. 概要

202X年5月28日に開催されたゼミにおいて、M1の舛田岳氏より「簡単な自己紹介とこれまでの研究、そしてこれからの研究について」と題した発表が行われました。本発表では、発表者の自己紹介に加え、学部時代に取り組んだ**大規模言語モデル（LLM）**の軽量化に関する研究の概要、およびその知見を基にした今後の修士研究計画が共有されました。

### 2. 主要な議論ポイント

#### 2.1. 自己紹介

* **氏名:** 舛田 岳（ますだ がく）
* **趣味・興味:** ライブ参戦、バレーボール（小中高）、ゲーム（ドラクエ、マイクラ、Valorant、マダミスなど）、Netflix、旅行、音楽鑑賞。特に音楽鑑賞とゲームへの深い関心がある。
* **技術スタック/使用ツール:**
  * **Frontend:** React, Next.js, Node.js, TypeScript
  * **Backend/Research:** Python, FastAPI, PyTorch, LangChain, TensorFlow, Hugging Face

#### 2.2. 学部時代の研究：大規模言語モデルの軽量化に関する研究

* **研究題目:** 「量子化と動的なLoRAによる大規模言語モデルの軽量化に関する研究」
* **大規模言語モデル（LLM）の現状と課題:**
  * ChatGPT、Claude、Geminiなどに代表されるLLMは非常に高性能で汎用的だが、いくつかの深刻な課題を抱えている。
  * **パラメータ数の巨大化:** 2018年の約3.4億パラメータから、2025年には約6850億パラメータへと爆発的に増加している。

1. テスト項目1
2. テスト項目2  
3. テスト項目3

通常のパラグラフテキストです。これは**太字**と*斜体*と`インラインコード`を含んでいます。
"""

    try:
        # PDFSummaryHandlerのインスタンスを作成（環境変数設定なしでテスト）
        handler = PDFSummaryHandler()
        
        # マークダウン変換をテスト
        print("=== マークダウン変換テスト ===")
        print("入力:")
        print(test_markdown)
        print("\n" + "="*50 + "\n")
        
        blocks = handler._create_blocks_from_markdown(test_markdown)
        
        print("出力:")
        print(f"生成されたブロック数: {len(blocks)}")
        print("\n各ブロックの詳細:")
        
        for i, block in enumerate(blocks):
            print(f"\nブロック {i+1}:")
            print(f"  タイプ: {block['type']}")
            
            if block['type'].startswith('heading_'):
                content = block[block['type']]['rich_text']
                text = ''.join([part['text']['content'] for part in content])
                print(f"  テキスト: {text}")
                
            elif block['type'] in ['bulleted_list_item', 'numbered_list_item']:
                content = block[block['type']]['rich_text']
                text = ''.join([part['text']['content'] for part in content])
                print(f"  テキスト: {text}")
                
            elif block['type'] == 'paragraph':
                content = block['paragraph']['rich_text']
                text = ''.join([part['text']['content'] for part in content])
                print(f"  テキスト: {text[:100]}{'...' if len(text) > 100 else ''}")
                
                # リッチテキストの詳細表示
                for j, part in enumerate(content):
                    if part['annotations']['bold'] or part['annotations']['italic'] or part['annotations']['code']:
                        print(f"    パート {j+1}: '{part['text']['content']}' - {part['annotations']}")
        
        print("\n=== テスト完了 ===")
        return True
        
    except Exception as e:
        print(f"テストエラー: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    test_markdown_conversion() 