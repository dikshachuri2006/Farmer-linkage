/**
 * FarmerLinkage — Multilingual Translation System (i18n)
 * Supports English (en), Marathi (mr), and Hindi (hi).
 */
const I18N = {
  currentLang: localStorage.getItem(CONFIG.STORAGE_KEYS.LANGUAGE) || CONFIG.DEFAULT_LANGUAGE,

  translations: {
    en: {
      // Navbar & Common
      "app.name": "FarmerLinkage",
      "nav.signin": "Sign In",
      "nav.register": "Create Account",
      "nav.logout": "Sign Out",
      "nav.dashboard": "My Dashboard",
      "nav.language": "Language",

      // Homepage Hero & Sections
      "hero.tag": "Digital Agricultural Marketplace",
      "hero.title": "Connecting Farmers Directly with Buyers",
      "hero.desc": "Discover agricultural produce, explore market prices, and connect farmers with buyers through a transparent digital marketplace.",
      "hero.btn.explore": "Explore Marketplace",
      "hero.btn.sell": "Start Selling",
      "hero.link.prices": "Explore Market Prices →",

      // Homepage Cards
      "cards.heading": "From Our Farms to Your Market",
      "cards.veg.title": "Fresh Vegetables",
      "cards.veg.desc": "Discover agricultural produce from farms.",
      "cards.grains.title": "Grains and Cereals",
      "cards.grains.desc": "Explore agricultural commodities.",
      "cards.farming.title": "Farmers and Farming",
      "cards.farming.desc": "Connect agricultural production with market opportunities.",

      // About Section
      "about.heading": "About FarmerLinkage",
      "about.desc": "FarmerLinkage is a digital agricultural marketplace built to strengthen direct connections between farmers and commercial buyers. By removing intermediaries and providing transparent price discovery, we facilitate fair trade agreements, reliable transactions, and improved farmgate net realizations.",

      // How it Works
      "how.heading": "How It Works",
      "how.farmer.title": "For Farmers",
      "how.farmer.step1": "Register and verify your agricultural profile.",
      "how.farmer.step2": "List your available produce lots with prices and location.",
      "how.farmer.step3": "Receive, review, and accept competitive buyer offers.",
      "how.farmer.step4": "Execute verified digital transactions and settlement receipts.",

      "how.buyer.title": "For Buyers",
      "how.buyer.step1": "Register and submit your commercial procurement profile.",
      "how.buyer.step2": "Browse available farmgate produce listings nationwide.",
      "how.buyer.step3": "Submit binding purchase offers directly to farmers.",
      "how.buyer.step4": "Track agreement fulfillment and settlement receipts.",

      // Market Prices Intro
      "prices.intro.heading": "Explore Agricultural Market Prices",
      "prices.intro.desc": "Stay informed with daily mandi arrival prices across state APMCs, helping you make data-driven selling and sourcing decisions.",
      "prices.intro.btn": "View All Market Prices",

      // CTA
      "cta.heading": "Join the FarmerLinkage Community",
      "cta.desc": "Whether you grow agricultural produce or source it for your business, start exploring FarmerLinkage today.",

      // Footer
      "footer.about": "About Us",
      "footer.how": "How It Works",
      "footer.marketplace": "Marketplace",
      "footer.prices": "Market Prices",
      "footer.contact": "Contact Us",
      "footer.signin": "Sign In",
      "footer.rights": "© 2026 FarmerLinkage. All rights reserved.",

      // Auth
      "auth.welcome": "Welcome Back",
      "auth.login.desc": "Sign in to access your farmer or buyer account.",
      "auth.identifier": "Email or Mobile Number",
      "auth.password": "Password",
      "auth.show.pwd": "Show",
      "auth.hide.pwd": "Hide",
      "auth.btn.signin": "Sign In",
      "auth.no.account": "Don't have an account?",
      "auth.register.link": "Create Account",
      "auth.have.account": "Already have an account?",
      "auth.login.link": "Sign In",
      "auth.home.link": "← Return to Homepage",

      "auth.register.title": "Create Account",
      "auth.register.desc": "Join FarmerLinkage as a Producer or Procuring Buyer.",
      "auth.fullname": "Full Name",
      "auth.email": "Email Address",
      "auth.phone": "10-Digit Mobile Number",
      "auth.confirmpwd": "Confirm Password",
      "auth.role": "I am joining as a",
      "auth.role.farmer": "Farmer / Producer",
      "auth.role.buyer": "Commercial Buyer",
      "auth.btn.register": "Create Account",

      // Marketplace & Details
      "market.heading": "Explore Agricultural Produce",
      "market.desc": "Discover available produce and connect directly with farmers through FarmerLinkage.",
      "market.search": "Search crops, varieties, or locations...",
      "market.filter.crop": "Filter by Crop",
      "market.filter.state": "State",
      "market.filter.minprice": "Min Price",
      "market.filter.maxprice": "Max Price",
      "market.btn.clear": "Clear Filters",
      "market.btn.details": "View Details",
      "market.btn.offer": "Make Offer",

      // Price Discovery
      "disc.heading": "Price Discovery and Net Realization",
      "disc.desc": "Compare potential net earnings across multiple mandis and buyer offers after transport and mandi deductions.",

      // Dashboard Common
      "dash.title": "Dashboard",
      "dash.profile": "My Profile",
      "dash.produce": "My Produce",
      "dash.addproduce": "Add Produce",
      "dash.offers": "Received Offers",
      "dash.myoffers": "My Offers",
      "dash.txns": "My Transactions",
      "dash.marketprices": "Market Prices",
      "dash.pricedisc": "Price Discovery",
      "dash.complaints": "Complaints & Disputes",
      "dash.admin.users": "User Management",
      "dash.admin.verify": "Buyer Verification",
      "dash.admin.markets": "Market Management",
      "dash.admin.reports": "Reports & Analytics",
    },

    mr: {
      // Marathi translations
      "app.name": "FarmerLinkage",
      "nav.signin": "साइन इन करा",
      "nav.register": "खाते तयार करा",
      "nav.logout": "बाहेर पडा",
      "nav.dashboard": "माझे डॅशबोर्ड",
      "nav.language": "भाषा",

      "hero.tag": "डिजिटल कृषी बाजारपेठ",
      "hero.title": "शेतकऱ्यांना थेट खरेदीदारांशी जोडणे",
      "hero.desc": "पारदर्शक डिजिटल बाजारपेठेद्वारे कृषी शेतमालाचा शोध घ्या, बाजारभाव तपासा आणि शेतकऱ्यांना खरेदीदारांशी जोडा.",
      "hero.btn.explore": "बाजारपेठ पहा",
      "hero.btn.sell": "विक्री सुरू करा",
      "hero.link.prices": "बाजारभाव पहा →",

      "cards.heading": "आमच्या शेतातून तुमच्या बाजारापर्यंत",
      "cards.veg.title": "ताजी भाजीपाला",
      "cards.veg.desc": "शेतातील ताजा कृषी माल मिळवा.",
      "cards.grains.title": "धान्य आणि कडधान्ये",
      "cards.grains.desc": "कृषी उत्पादनांची माहिती मिळवा.",
      "cards.farming.title": "शेतकरी आणि शेती",
      "cards.farming.desc": "शेती उत्पादनाला बाजारातील संधींशी जोडा.",

      "about.heading": "FarmerLinkage बद्दल",
      "about.desc": "FarmerLinkage ही शेतकरी आणि व्यापारी यांच्यात थेट व्यापार घडवून आणणारी डिजिटल बाजारपेठ आहे. मध्यस्थांशिवाय पारदर्शक किंमत निश्चिती आणि वाजवी शेतमाल दर मिळवून देणे हा आमचा उद्देश आहे.",

      "how.heading": "हे कसे कार्य करते",
      "how.farmer.title": "शेतकऱ्यांसाठी",
      "how.farmer.step1": "नोंदणी करा आणि प्रोफाइल पूर्ण करा.",
      "how.farmer.step2": "तुमच्या शेतमालाची किंमत आणि माहिती नोंदवा.",
      "how.farmer.step3": "खरेदीदारांच्या ऑफर्स तपासा आणि स्वीकारा.",
      "how.farmer.step4": "डिजिटल पावतीसह सुरक्षित व्यवहार पूर्ण करा.",

      "how.buyer.title": "खरेदीदारांसाठी",
      "how.buyer.step1": "नोंदणी करा आणि व्यापारी प्रोफाइल भरा.",
      "how.buyer.step2": "देशभरातील थेट शेतमाल यादी पहा.",
      "how.buyer.step3": "शेतकऱ्यांना थेट खरेदी ऑफर पाठवा.",
      "how.buyer.step4": "व्यवहार आणि पावती सुरक्षितपणे व्यवस्थापित करा.",

      "prices.intro.heading": "कृषी बाजारभाव तपासा",
      "prices.intro.desc": "विविध कृषी उत्पन्न बाजार समित्यांमधील दैनंदिन बाजारभाव तपासून योग्य निर्णय घ्या.",
      "prices.intro.btn": "सर्व बाजारभाव पहा",

      "cta.heading": "FarmerLinkage परिवारात सामील व्हा",
      "cta.desc": "तुम्ही शेतकरी असा किंवा व्यापारी, आजच FarmerLinkage सह व्यवहार सुरू करा.",

      "footer.about": "आमच्याबद्दल",
      "footer.how": "कार्यपद्धती",
      "footer.marketplace": "बाजारपेठ",
      "footer.prices": "बाजारभाव",
      "footer.contact": "संपर्क",
      "footer.signin": "साइन इन करा",
      "footer.rights": "© 2026 FarmerLinkage. सर्व हक्क राखीव.",

      "auth.welcome": "पुन्हा आपले स्वागत आहे",
      "auth.login.desc": "आपल्या खात्यात प्रवेश करण्यासाठी साइन इन करा.",
      "auth.identifier": "ईमेल किंवा १० अंकी मोबाईल नंबर",
      "auth.password": "पासवर्ड",
      "auth.show.pwd": "दाखवा",
      "auth.hide.pwd": "लपवा",
      "auth.btn.signin": "साइन इन करा",
      "auth.no.account": "नवीन खाते हवे आहे?",
      "auth.register.link": "खाते तयार करा",
      "auth.have.account": "आधीच खाते आहे?",
      "auth.login.link": "साइन इन करा",
      "auth.home.link": "← मुख्यपृष्ठावर परत जा",

      "auth.register.title": "खाते तयार करा",
      "auth.register.desc": "शेतकरी किंवा खरेदीदार म्हणून नोंदणी करा.",
      "auth.fullname": "पूर्ण नाव",
      "auth.email": "ईमेल पत्ता",
      "auth.phone": "१० अंकी मोबाईल नंबर",
      "auth.confirmpwd": "पासवर्ड पुष्टी करा",
      "auth.role": "खाते प्रकार",
      "auth.role.farmer": "शेतकरी / उत्पादक",
      "auth.role.buyer": "खरेदीदार / व्यापारी",
      "auth.btn.register": "खाते तयार करा",

      "market.heading": "कृषी शेतमाल शोधा",
      "market.desc": "उपलब्ध शेतमाल पहा आणि थेट शेतकऱ्यांशी संपर्क साधा.",
      "market.search": "पीक, जात किंवा ठिकाण शोधा...",
      "market.filter.crop": "पीक निवडा",
      "market.filter.state": "राज्य",
      "market.filter.minprice": "किमान किंमत",
      "market.filter.maxprice": "कमाल किंमत",
      "market.btn.clear": "फिल्टर्स साफ करा",
      "market.btn.details": "तपशील पहा",
      "market.btn.offer": "ऑफर द्या",

      "disc.heading": "किंमत शोध आणि निव्वळ नफा",
      "disc.desc": "वाहतूक आणि बाजार खर्च वजा जाता कोणत्या बाजारात जास्त नफा मिळतो ते तपासा.",

      "dash.title": "डॅशबोर्ड",
      "dash.profile": "माझी प्रोफाइल",
      "dash.produce": "माझा शेतमाल",
      "dash.addproduce": "शेतमाल जोडा",
      "dash.offers": "प्राप्त ऑफर्स",
      "dash.myoffers": "माझ्या ऑफर्स",
      "dash.txns": "माझे व्यवहार",
      "dash.marketprices": "बाजारभाव",
      "dash.pricedisc": "किंमत शोध",
      "dash.complaints": "तक्रारी व वाद निवारण",
      "dash.admin.users": "वापरकर्ता व्यवस्थापन",
      "dash.admin.verify": "खरेदीदार पडताळणी",
      "dash.admin.markets": "बाजार व्यवस्थापन",
      "dash.admin.reports": "अहवाल व आकडेवारी",
    },

    hi: {
      // Hindi translations
      "app.name": "FarmerLinkage",
      "nav.signin": "साइन इन करें",
      "nav.register": "खाता बनाएं",
      "nav.logout": "लॉग आउट",
      "nav.dashboard": "डैशबोर्ड",
      "nav.language": "भाषा",

      "hero.tag": "डिजिटल कृषि बाज़ार",
      "hero.title": "किसानों को सीधे खरीदारों से जोड़ना",
      "hero.desc": "पारदर्शी डिजिटल बाज़ार के माध्यम से कृषि उपज खोजें, मंडी भाव देखें और किसानों को खरीदारों से जोड़ें।",
      "hero.btn.explore": "बाज़ार देखें",
      "hero.btn.sell": "बिक्री शुरू करें",
      "hero.link.prices": "मंडी भाव देखें →",

      "cards.heading": "हमारे खेतों से आपकी मंडी तक",
      "cards.veg.title": "ताजी सब्जियां",
      "cards.veg.desc": "खेतों से सीधी ताजी उपज पाएं।",
      "cards.grains.title": "अनाज और दलहन",
      "cards.grains.desc": "कृषि जिंसों की विस्तृत श्रृंखला खोजें।",
      "cards.farming.title": "किसान और किसानी",
      "cards.farming.desc": "कृषि उत्पादन को नए बाज़ारों से जोड़ें।",

      "about.heading": "FarmerLinkage के बारे में",
      "about.desc": "FarmerLinkage किसानों और व्यापारिक खरीदारों के बीच सीधा संपर्क स्थापित करने वाला डिजिटल मंच है। बिचौलियों को हटाकर और पारदर्शी मूल्य निर्धारण प्रदान करके, हम उचित व्यापार और बेहतर मुनाफा सुनिश्चित करते हैं।",

      "how.heading": "यह कैसे काम करता है",
      "how.farmer.title": "किसानों के लिए",
      "how.farmer.step1": "पंजीकरण करें और अपनी प्रोफ़ाइल पूरी करें।",
      "how.farmer.step2": "अपनी उपज और अपेक्षित मूल्य दर्ज करें।",
      "how.farmer.step3": "खरीदारों से ऑफ़र प्राप्त करें और स्वीकार करें।",
      "how.farmer.step4": "डिजिटल रसीद के साथ व्यापार पूरा करें।",

      "how.buyer.title": "खरीदारों के लिए",
      "how.buyer.step1": "पंजीकरण करें और व्यावसायिक प्रोफ़ाइल सत्यापित करें।",
      "how.buyer.step2": "देशभर की उपलब्ध उपज सूची ब्राउज़ करें।",
      "how.buyer.step3": "किसानों को सीधे खरीद ऑफ़र भेजें।",
      "how.buyer.step4": "सौदा और रसीद डिजिटल रूप से प्रबंधित करें।",

      "prices.intro.heading": "कृषि मंडी भाव देखें",
      "prices.intro.desc": "विभिन्न मंडियों के दैनिक आवक भाव देखकर सही और लाभदायक निर्णय लें।",
      "prices.intro.btn": "सभी मंडी भाव देखें",

      "cta.heading": "FarmerLinkage समुदाय से जुड़ें",
      "cta.desc": "चाहे आप किसान हों या खरीदार, आज ही FarmerLinkage के साथ जुड़ें।",

      "footer.about": "हमारे बारे में",
      "footer.how": "प्रक्रिया",
      "footer.marketplace": "बाज़ार",
      "footer.prices": "मंडी भाव",
      "footer.contact": "संपर्क करें",
      "footer.signin": "साइन इन करें",
      "footer.rights": "© 2026 FarmerLinkage. सर्वाधिकार सुरक्षित।",

      "auth.welcome": "वापसी पर स्वागत है",
      "auth.login.desc": "अपने खाते में प्रवेश करने के लिए साइन इन करें।",
      "auth.identifier": "ईमेल या १० अंकों का मोबाइल नंबर",
      "auth.password": "पासवर्ड",
      "auth.show.pwd": "दिखाएं",
      "auth.hide.pwd": "छिपाएं",
      "auth.btn.signin": "साइन इन करें",
      "auth.no.account": "नया खाता चाहिए?",
      "auth.register.link": "खाता बनाएं",
      "auth.have.account": "पहले से खाता है?",
      "auth.login.link": "साइन इन करें",
      "auth.home.link": "← मुख्य पृष्ठ पर लौटें",

      "auth.register.title": "खाता बनाएं",
      "auth.register.desc": "किसान या खरीदार के रूप में पंजीकरण करें।",
      "auth.fullname": "पूरा नाम",
      "auth.email": "ईमेल पता",
      "auth.phone": "१० अंकों का मोबाइल नंबर",
      "auth.confirmpwd": "पासवर्ड पुष्टि करें",
      "auth.role": "खाते का प्रकार",
      "auth.role.farmer": "किसान / उत्पादक",
      "auth.role.buyer": "व्यापारिक खरीदार",
      "auth.btn.register": "खाता बनाएं",

      "market.heading": "कृषि उपज खोजें",
      "market.desc": "उपलब्ध उपज ब्राउज़ करें और सीधे किसानों से जुड़ें।",
      "market.search": "फसल, किस्म या स्थान खोजें...",
      "market.filter.crop": "फसल चुनें",
      "market.filter.state": "राज्य",
      "market.filter.minprice": "न्यूनतम मूल्य",
      "market.filter.maxprice": "अधिकतम मूल्य",
      "market.btn.clear": "फ़िल्टर हटाएं",
      "market.btn.details": "विवरण देखें",
      "market.btn.offer": "ऑफ़र दें",

      "disc.heading": "मूल्य खोज और वास्तविक मुनाफा",
      "disc.desc": "परिवहन और मंडी खर्च घटाकर तुलना करें कि किस मंडी में सबसे अधिक शुद्ध लाभ होगा।",

      "dash.title": "डैशबोर्ड",
      "dash.profile": "मेरी प्रोफ़ाइल",
      "dash.produce": "मेरी उपज",
      "dash.addproduce": "उपज जोड़ें",
      "dash.offers": "प्राप्त ऑफ़र",
      "dash.myoffers": "मेरे ऑफ़र",
      "dash.txns": "मेरे सौदे",
      "dash.marketprices": "मंडी भाव",
      "dash.pricedisc": "मूल्य खोज",
      "dash.complaints": "शिकायत व विवाद",
      "dash.admin.users": "उपयोगकर्ता प्रबंधन",
      "dash.admin.verify": "खरीदार सत्यापन",
      "dash.admin.markets": "मंडी प्रबंधन",
      "dash.admin.reports": "रिपोर्ट और विश्लेषण",
    }
  },

  /**
   * Translate a key into the active language
   */
  t(key, fallback = '') {
    const langObj = this.translations[this.currentLang] || this.translations.en;
    return langObj[key] || this.translations.en[key] || fallback || key;
  },

  /**
   * Set preferred language and apply updates across the DOM
   */
  setLanguage(lang) {
    if (!CONFIG.SUPPORTED_LANGUAGES.includes(lang)) {
      lang = CONFIG.DEFAULT_LANGUAGE;
    }
    this.currentLang = lang;
    localStorage.setItem(CONFIG.STORAGE_KEYS.LANGUAGE, lang);
    this.applyTranslations();

    // Sync any language selector dropdown in the DOM
    const selectors = document.querySelectorAll('.lang-select');
    selectors.forEach(sel => {
      sel.value = lang;
    });

    window.dispatchEvent(new CustomEvent('language-changed', { detail: { lang } }));
  },

  /**
   * Scan DOM for elements with data-i18n and data-i18n-placeholder and translate them
   */
  applyTranslations() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
      const key = el.getAttribute('data-i18n');
      if (key) {
        el.textContent = this.t(key);
      }
    });

    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
      const key = el.getAttribute('data-i18n-placeholder');
      if (key) {
        el.setAttribute('placeholder', this.t(key));
      }
    });
  },

  /**
   * Initialize translation system on page load
   */
  init() {
    this.applyTranslations();
  }
};

// Auto-run on DOMContentLoaded
document.addEventListener('DOMContentLoaded', () => {
  I18N.init();
});
