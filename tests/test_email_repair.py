from pdf_html_polish.email_repair import repair_split_visible_emails


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


def test_repair_split_visible_emails_joins_named_local_dot() -> None:
    text = (
        "Rachel Blue: University of Pennsylvania, Philadelphia, PA. "
        "rachel. blue@pennmedicine.upenn.edu."
    )

    assert "rachel.blue@pennmedicine.upenn.edu" in repair_split_visible_emails(text)


def test_repair_split_visible_emails_keeps_sentence_boundary() -> None:
    text = "Correspondence should be addressed. jamesbarresemd@gmail.com."

    assert repair_split_visible_emails(text) == text
