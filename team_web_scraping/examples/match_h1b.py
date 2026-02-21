from job_scraper.core.sponsor_checker import SponsorChecker

def test():
    sc = SponsorChecker()
    sponsors = [
        "Google",
        "Microsoft",
        "Amazon",
        "Apple",
        "Meta",
        "Deloitte",
        "Infosys",
        "Tata Consultancy Services",
    ]

    non_sponsors = [
        "Moms Little Bakery",
        "Sunset Plumbing Services",
        "Joe's Auto Repair",
    ]

    print("Test 1")
    for name in sponsors:
        print(name, sc.check(name))
    print()

    print("Test 2")
    for name in non_sponsors:
        print(name, sc.check(name))

if __name__ == "__main__":
    test()
