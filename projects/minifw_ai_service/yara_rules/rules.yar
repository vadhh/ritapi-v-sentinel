rule gambling_keywords {
    meta:
        description = "Detects gambling related keywords"
        severity = "medium"
        category = "gambling"
    strings:
        $s1 = "slot" nocase
        $s2 = "casino" nocase
        $s3 = "judionline" nocase
    condition:
        any of them
}

rule suspicious_commands {
    meta:
        description = "Detects suspicious command lines"
        severity = "high"
        category = "security_risk"
    strings:
        $p1 = "powershell" nocase
        $p2 = "base64" nocase
    condition:
        all of them
}
