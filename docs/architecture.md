# Архитектура

Слои проекта: discovery → manifest → fetch/cache → formats → audit/validate →
glossary/merge → providers → reports → patches/deployment.

English задаёт структуру, Ukrainian сохраняется, Russian используется как
справочный QA-слой. Каждая операция должна быть повторяемой и неразрушающей.

