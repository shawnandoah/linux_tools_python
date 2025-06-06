# Extract properties from a cpp implementation file
def parse_cpp_properties(cpp_path):
    content = Path(cpp_path).read_text()

    # Extract init(...) { ... } block
    init_pattern = r'\b\w+::\s*init\s*\([^)]*\)\s*\{'
    init_block = extract_function_block(content, init_pattern)
    if not init_block:
        return []



    #option 1
    line = 'M_model = vm->getStringSetting(m_cfgTag + ".propertyName2", "defaultstr");'
    
    match = re.search(
        r'vm->get\w+Setting\(\s*m_cfgTag\s*\+\s*"\.([^"]+)"\s*(?:,\s*([^)]+))?\)',
        line
    )
    
    if match:
        print("Property Name:", match.group(1))  # propertyName2
        print("Default Value:", match.group(2))  # "defaultstr"
    else:
        print("No match found.")

    #option 2
    # Use re.findall() for consistent pattern like we did for registrations
   # setting_pattern = re.findall(
        # r'vm->get\w+Setting\s*\(\s*m_cfgTag\s*\+\s*"\.([^"\']+)"\s*(?:,\s*([\w\.\-]+|\"[^\"]*\"|\'[^\']*\'))?\)',
    setting_pattern = re.findall(
    r'Registrator<\s*Calculator\s*>.*?"([^"]+)"\s*,\s*ObjectFactory<\s*Calculator\s*>::DFactoryMethod<\s*([^>\s]+)\s*>',
        init_block,
        re.DOTALL
    )

    properties = []
    for prop_name, default_value in setting_pattern:
        properties.append((prop_name, default_value.strip() if default_value else ''))

    return properties


