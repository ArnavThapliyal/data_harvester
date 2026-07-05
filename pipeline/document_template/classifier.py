class DocumentClassifier:
    def classify(self, filename: str, text: str) -> str:
        search_text = f"{filename}\n{text}"

        for rule in self.rules:
            if re.search(rule.pattern, search_text, re.I):
                return rule.doc_type

        return "unknown_filing"