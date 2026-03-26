import pandas as pd
import re

def main():
    csv_file = r"evaluation/data/test_subset_fixes.csv"
    print(f"Loading {csv_file}")
    df = pd.read_csv(csv_file)
    
    # We need to extract <fixed_block_content><![CDATA[ ... ]]></fixed_block_content>
    # or just <fixed_block_content> ... </fixed_block_content>
    
    extracted_contents = []
    
    for _, row in df.iterrows():
        text = str(row.get("fixed_block_content", ""))
        
        # Try to find fixed_block_content
        match = re.search(r'<fixed_block_content>(.*?)</fixed_block_content>', text, re.DOTALL)
        if match:
            content = match.group(1).strip()
            # Remove CDATA if present
            content = re.sub(r'^<!\[CDATA\[|\]\]>$', '', content, flags=re.DOTALL).strip()
            extracted_contents.append(content)
        else:
            # Maybe the LLM didn't wrap it in tags? Just try stripping CDATA
            clean_text = re.sub(r'^<!\[CDATA\[|\]\]>$', '', text, flags=re.DOTALL).strip()
            extracted_contents.append(clean_text)
            
    df['fixed_block_content'] = extracted_contents
    
    parsed_count = df['fixed_block_content'].notna().sum()
    print(f"Successfully extracted {parsed_count} / {len(df)} blocks.")
    
    df.to_csv(csv_file, index=False)
    print("Saved extracted blocks back to CSV.")

if __name__ == "__main__":
    main()
