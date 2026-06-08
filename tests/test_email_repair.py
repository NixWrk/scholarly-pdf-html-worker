from zoteropdf2md.email_repair import repair_split_visible_emails


def test_repair_split_visible_emails_joins_labeled_local_dot() -> None:
    assert repair_split_visible_emails("Email: jan. krhut@fno.cz") == "Email: jan.krhut@fno.cz"
    assert repair_split_visible_emails("Contact: valeriaanna. sovrano@unitn.it") == (
        "Contact: valeriaanna.sovrano@unitn.it"
    )


def test_repair_split_visible_emails_joins_domain_spaces() -> None:
    assert repair_split_visible_emails("e-mail: lotfi_merabet@ meei.harvard.edu") == (
        "e-mail: lotfi_merabet@meei.harvard.edu"
    )
    assert repair_split_visible_emails("Reach margaret.tarampi@psych .utah.edu") == (
        "Reach margaret.tarampi@psych.utah.edu"
    )
